import asyncio


def test_stream_csv_uses_sqlalchemy_text_and_row_mapping(monkeypatch):
    class FakeRow:
        def __init__(self, mapping: dict):
            self._mapping = mapping

    class FakeResult:
        def __init__(self, rows):
            self._rows = rows

        def __aiter__(self):
            self._iter = iter(self._rows)
            return self

        async def __anext__(self):
            try:
                return next(self._iter)
            except StopIteration:
                raise StopAsyncIteration

    class FakeConn:
        async def stream(self, clause):
            return FakeResult(
                [
                    FakeRow({"a": 1, "b": "x"}),
                    FakeRow({"a": 2, "b": "y"}),
                ]
            )

    class FakeConnectCtx:
        async def __aenter__(self):
            return FakeConn()

        async def __aexit__(self, exc_type, exc, tb):
            return False

    class FakeAsyncEngine:
        def connect(self):
            return FakeConnectCtx()

    class FakeDB:
        async_engine = FakeAsyncEngine()

    def fake_get_query_db(project_id: int):
        return FakeDB()

    monkeypatch.setattr("src.api.routes.query.get_query_db", fake_get_query_db)

    async def main():
        from src.api.routes.query import stream_csv

        resp = await stream_csv("select 1", project_id=1)
        chunks = []
        async for chunk in resp.body_iterator:
            chunks.append(chunk)
            if len(chunks) >= 3:
                break
        return chunks

    chunks = asyncio.run(main())
    rendered = []
    for c in chunks:
        if isinstance(c, bytes):
            rendered.append(c.decode("utf-8"))
        else:
            rendered.append(str(c))
    assert any("a,b" in c for c in rendered)
