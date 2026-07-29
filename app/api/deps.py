from functools import lru_cache
from typing import Optional
from fastapi import Depends
from app.config import settings
from app.data.database import Database
from app.data.cache import RedisCache
from app.pipeline.analyzer import Analyzer
from app.pipeline.cache import MultiLevelCache


class AppState:
    def __init__(self):
        self._db: Optional[Database] = None
        self._cache: Optional[RedisCache] = None
        self._analyzer: Optional[Analyzer] = None
        self._pipeline_cache: Optional[MultiLevelCache] = None
        self._rag_engine = None

    def init(self, db: Database, cache: Optional[RedisCache] = None, rag_engine=None):
        self._db = db
        self._cache = cache
        self._rag_engine = rag_engine
        self._pipeline_cache = MultiLevelCache(redis=cache, db=db)
        self._analyzer = Analyzer(db, cache=self._pipeline_cache, rag_engine=rag_engine)

    @property
    def db(self) -> Database:
        if not self._db:
            raise RuntimeError("Database not initialized")
        return self._db

    @property
    def cache(self) -> Optional[RedisCache]:
        return self._cache

    @property
    def pipeline_cache(self) -> MultiLevelCache:
        if not self._pipeline_cache:
            raise RuntimeError("Pipeline cache not initialized")
        return self._pipeline_cache

    @property
    def analyzer(self) -> Analyzer:
        if not self._analyzer:
            raise RuntimeError("Analyzer not initialized")
        return self._analyzer


app_state = AppState()


def get_db() -> Database:
    return app_state.db


def get_cache() -> Optional[RedisCache]:
    return app_state.cache


def get_analyzer() -> Analyzer:
    return app_state.analyzer


def get_pipeline_cache() -> MultiLevelCache:
    return app_state.pipeline_cache
