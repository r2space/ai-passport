import asyncio
from datetime import datetime, timezone
import importlib.util
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest

SPEC = importlib.util.spec_from_file_location('completion_bridge', Path(__file__).parents[1] / 'tools/codex_bridge.py')
bridge = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(bridge)


class CompletionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.home = Path(self.temp.name)
        self.sessions = self.home / 'sessions'
        self.sessions.mkdir()

    def session(self, name, thread=None, source='vscode'):
        path = self.sessions / (name + '.jsonl')
        path.write_text(json.dumps({'type': 'session_meta', 'payload': {'id': thread or name, 'source': source}}) + '\n')
        return path

    def event(self, path, kind, turn='turn-1', root=None, stamp=None):
        record = {'type': 'event_msg', 'payload': {'type': kind, 'turn_id': turn, 'root_turn_id': root or turn}}
        if stamp: record['timestamp'] = stamp
        with path.open('a') as stream: stream.write(json.dumps(record) + '\n')

    def test_parent_stays_running_while_subagent_finishes(self):
        parent = self.session('parent')
        child = self.session('child', source={'subagent': {'other': 'worker'}})
        w = bridge.SessionWatcher(self.home)
        self.event(parent, 'task_started')
        self.event(child, 'task_started', 'child-turn', root='turn-1')
        self.event(child, 'task_complete', 'child-turn', root='turn-1')
        w.poll()
        self.assertEqual((w.running_count, w.completion_sequence), (1, 0))
        self.event(parent, 'task_complete')
        w.poll()
        self.assertEqual((w.running_count, w.completion_sequence), (0, 1))

    def test_subagent_source_variants_never_count(self):
        for source in ('subagent', {'subAgent': {}}, {'sub_agent': {'other': 'worker'}}):
            with self.subTest(source=source):
                path = self.session('child', source=source)
                w = bridge.SessionWatcher(self.home)
                self.event(path, 'task_started')
                self.event(path, 'task_complete')
                w.poll()
                self.assertEqual((w.running_count, w.completion_sequence), (0, 0))

    def test_each_conversation_completes_independently(self):
        a, b = self.session('a'), self.session('b')
        w = bridge.SessionWatcher(self.home)
        self.event(a, 'task_started'); self.event(b, 'task_started')
        w.poll()
        self.event(a, 'task_complete'); w.poll()
        self.assertEqual((w.running_count, w.completion_sequence), (1, 1))
        self.event(b, 'task_complete'); w.poll()
        self.assertEqual((w.running_count, w.completion_sequence), (0, 2))

    def test_duplicates_and_unmatched_completion_do_not_count(self):
        p = self.session('root'); w = bridge.SessionWatcher(self.home)
        self.event(p, 'task_complete', 'unknown')
        self.event(p, 'task_started'); self.event(p, 'task_complete')
        self.event(p, 'task_complete'); self.event(p, 'task_started'); self.event(p, 'task_complete')
        w.poll()
        self.assertEqual(w.completion_sequence, 1)

    def test_same_turn_in_two_rollouts_counts_once(self):
        a = self.session('a', thread='shared'); b = self.session('b', thread='shared')
        w = bridge.SessionWatcher(self.home)
        self.event(a, 'task_started'); self.event(b, 'task_started'); w.poll()
        self.assertEqual(w.running_count, 1)
        self.event(a, 'task_complete'); self.event(b, 'task_complete'); w.poll()
        self.assertEqual(w.completion_sequence, 1)

    def test_abort_cannot_later_be_reported_as_success(self):
        p = self.session('root'); w = bridge.SessionWatcher(self.home)
        self.event(p, 'task_started'); self.event(p, 'turn_aborted'); w.poll()
        self.assertEqual((w.running_count, w.completion_sequence), (0, 0))
        self.event(p, 'task_started', 'next')
        self.event(p, 'task_complete', 'turn-1'); w.poll()
        self.assertEqual((w.running_count, w.completion_sequence), (1, 0))
        self.event(p, 'task_complete', 'next'); w.poll()
        self.assertEqual(w.completion_sequence, 1)

    def test_message_phase_is_not_a_terminal_event(self):
        p = self.session('root'); w = bridge.SessionWatcher(self.home)
        self.event(p, 'task_started'); w.poll()
        with p.open('a') as f:
            f.write(json.dumps({'type': 'response_item', 'payload': {'type': 'message', 'role': 'assistant', 'phase': 'final_answer', 'content': 'ignored'}}) + '\n')
        w.poll()
        self.assertEqual((w.running_count, w.completion_sequence), (1, 0))
        self.event(p, 'task_complete'); w.poll()
        self.assertEqual(w.completion_sequence, 1)

    def test_nested_turn_without_subagent_metadata_is_ignored(self):
        p = self.session('root'); w = bridge.SessionWatcher(self.home)
        self.event(p, 'task_started', 'child', root='parent')
        self.event(p, 'task_complete', 'child', root='parent'); w.poll()
        self.assertEqual((w.running_count, w.completion_sequence), (0, 0))

    def test_partial_record_is_retried_after_the_newline(self):
        p = self.session('root'); w = bridge.SessionWatcher(self.home)
        start = json.dumps({'type': 'event_msg', 'payload': {'type': 'task_started', 'turn_id': 't'}}) + '\n'
        with p.open('a') as f: f.write(start[:-2])
        w.poll(); self.assertEqual(w.running_count, 0)
        with p.open('a') as f: f.write(start[-2:])
        w.poll(); self.assertEqual(w.running_count, 1)
        end = json.dumps({'type': 'event_msg', 'payload': {'type': 'task_complete', 'turn_id': 't'}})
        with p.open('a') as f: f.write(end)
        w.poll(); self.assertEqual(w.completion_sequence, 0)
        with p.open('a') as f: f.write('\n')
        w.poll(); w.poll(); self.assertEqual(w.completion_sequence, 1)

    def test_startup_recovers_long_running_turn_without_alerting(self):
        p = self.session('root')
        self.event(p, 'task_started')
        with p.open('a') as f: f.write(json.dumps({'type': 'response_item', 'payload': {'ignored': 'x' * (2 * 1024 * 1024 + 1)}}) + '\n')
        w = bridge.SessionWatcher(self.home)
        self.assertEqual((w.running_count, w.completion_sequence), (1, 0))
        self.event(p, 'task_complete'); w.poll()
        self.assertEqual(w.completion_sequence, 1)

    def test_newly_discovered_old_history_is_silent(self):
        w = bridge.SessionWatcher(self.home)
        p = self.session('resumed')
        self.event(p, 'task_started', stamp='2000-01-01T00:00:00Z')
        self.event(p, 'task_complete', stamp='2000-01-01T00:00:01Z')
        w.poll()
        self.assertEqual((w.running_count, w.completion_sequence), (0, 0))

    def test_reconnect_discards_offline_completions(self):
        p = self.session('root'); w = bridge.SessionWatcher(self.home)
        self.event(p, 'task_started'); self.event(p, 'task_complete')
        w.poll(notify=False)
        self.assertEqual((w.running_count, w.completion_sequence), (0, 0))
        self.event(p, 'task_started', 'online'); self.event(p, 'task_complete', 'online')
        w.poll(); self.assertEqual(w.completion_sequence, 1)

    def test_copied_rollout_cannot_replay_a_completed_turn(self):
        p = self.session('root'); w = bridge.SessionWatcher(self.home)
        self.event(p, 'task_started'); self.event(p, 'task_complete'); w.poll()
        copy = self.sessions / 'copy.jsonl'; copy.write_bytes(p.read_bytes())
        w.poll(); self.assertEqual(w.completion_sequence, 1)


class NotificationTransportTests(unittest.IsolatedAsyncioTestCase):
    async def test_two_completions_are_two_confirmed_events_not_a_counter_jump(self):
        client = SimpleNamespace(services=SimpleNamespace(get_characteristic=lambda _uuid: SimpleNamespace(max_write_without_response_size=100)))
        frames, responses, buf = [], [], bytearray()
        async def write(_uuid, data, response):
            responses.append(response); buf.extend(data)
            while b'\n' in buf:
                line, _, rest = buf.partition(b'\n'); buf[:] = rest; frames.append(json.loads(line))
        client.write_gatt_char = write
        watcher = SimpleNamespace(completion_sequence=12, running_count=1)
        self.assertEqual(await bridge.send_completion_notifications(client, {}, watcher, 1, 10), 12)
        self.assertEqual([f['codex']['completion_seq'] for f in frames], [11, 12])
        self.assertTrue(all(f['codex']['completion_event'] for f in frames))
        self.assertTrue(all(responses))
        normal = json.loads(bridge.heartbeat_payload({}, watcher))
        self.assertFalse(normal['codex']['completion_event'])

    async def test_subagents_are_not_counted_as_running_conversations(self):
        server = bridge.CodexAppServer()
        async def request(*_args, **_kwargs):
            return {'data': [{'source': 'vscode', 'status': {'type': 'active'}},
                             {'source': {'subAgent': {}}, 'status': {'type': 'active'}},
                             {'threadSource': {'subagent': {}}, 'status': {'type': 'active'}}]}
        server.request = request
        self.assertEqual(await server.running_task_count(), 1)


if __name__ == '__main__':
    unittest.main()
