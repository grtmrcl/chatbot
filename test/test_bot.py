import ast
import pathlib


class TestDailyEventRemindSchedule:
    """daily_event_remindタスクのスケジュール設定"""

    def _get_loop_time_node(self):
        bot_path = pathlib.Path(__file__).parent.parent / "bot.py"
        source = bot_path.read_text()
        tree = ast.parse(source)
        for node in ast.walk(tree):
            if isinstance(node, ast.AsyncFunctionDef) and node.name == "daily_event_remind":
                for decorator in node.decorator_list:
                    if isinstance(decorator, ast.Call):
                        for keyword in decorator.keywords:
                            if keyword.arg == "time":
                                return keyword.value
        return None

    def test_通知時刻が正午12時に設定されている(self):
        # Given: bot.pyのソースコードにdaily_event_remindのループ設定がある
        loop_time = self._get_loop_time_node()

        # When: tasks.loopのtime引数を解析する

        # Then: datetime.time(12, 0, ...) であること
        assert loop_time is not None, "tasks.loopのtime引数が見つかりません"
        assert isinstance(loop_time, ast.Call)
        args = loop_time.args
        assert len(args) >= 2, "datetime.timeの引数が不足しています"
        assert args[0].value == 12, f"時間が12ではありません: {args[0].value}"
        assert args[1].value == 0, f"分が0ではありません: {args[1].value}"

    def test_通知時刻にJSTタイムゾーンが指定されている(self):
        # Given: bot.pyのソースコードにdaily_event_remindのループ設定がある
        loop_time = self._get_loop_time_node()

        # When: tasks.loopのtime引数のキーワード引数を解析する

        # Then: tzinfo=JST が指定されていること
        assert loop_time is not None, "tasks.loopのtime引数が見つかりません"
        tzinfo_kwarg = next(
            (kw for kw in loop_time.keywords if kw.arg == "tzinfo"),
            None,
        )
        assert tzinfo_kwarg is not None, "tzinfo引数が指定されていません"
        assert isinstance(tzinfo_kwarg.value, ast.Name)
        assert tzinfo_kwarg.value.id == "JST", f"JSTではありません: {tzinfo_kwarg.value.id}"
