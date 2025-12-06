# dataManager/__init__.py
from .redis_data_manager import RedisDataManager, get_data_manager

__all__ = ['RedisDataManager', 'get_data_manager']
