import os
import sys
import unittest
import traceback
import inspect
from easydi import *

class ProviderA:
    def __init__(self, value):
        self._value = "{}.{}".format("A", value)

    @property
    def value(self):
        return self._value

class ProviderB:
    def __init__(self, value):
        self._value = "{}.{}".format("B", value)

    @property
    def value(self):
        return self._value

class ServiceA:
    def __init__(self, provider):
        if not isinstance(provider, (ProviderA, ProviderB)):
            raise Exception("Invalid Provider")

        self._provider = provider

    @property
    def provider(self):
        return self._provider

class ServiceB:
    def __init__(self, config_value):
        self._config_value = config_value

    def get(self):
        return self._config_value

class ServiceC:
    def __init__(self, providers):
        self._providers = providers

    @property
    def providers(self):
        return self._providers

    def has(self, provider_class):
        for p in self._providers:
            if isinstance(p, provider_class):
                return True
        return False

class Config:
    def __init__(self):
        self._config = {
            "section1" : {
                "key1" : "1",
                "key2" : 2
            }
        }

    def get(self, name, placeholder=None, value_format=None):
        section, key = name.split(".")

        value = None
        try:
            value = self._config[section][key]
        except:
            value = placeholder

        if value_format is not None:
            return value_format(value)
        return value

    def set(self, section, key, value):
        if section not in self._config:
            self._config[section] = {}

        self._config[section][key] = value

class EasyDiTest(unittest.TestCase):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self._container = Container()
        self._container.register(Config, _config=True) 
        self._config = self.retrieve_instance(Config).instance()

    def retrieve_class_path(self, obj):
        if not inspect.isclass(obj):
            raise Exception("Object must be a class")
        paths = obj.__module__.split(".")
        paths.append(obj.__qualname__)

        return paths

    def retrieve_instance(self, obj):
        class_path = self.retrieve_class_path(obj)
        for path in class_path:
            if isinstance(obj, ObjectFactoryMap):
                obj = getattr(obj, path)
            else:
                obj = getattr(self._container, path)
        return obj


class TestDependency(EasyDiTest):
    def test(self):
        self._container.register(ProviderA, DependencyConfig("section1.key1"))
        self._container.register(ServiceA, ProviderA)

        s1 = self.retrieve_instance(ServiceA).instance()
        s2 = self.retrieve_instance(ServiceA).instance()
        s3 = self.retrieve_instance(ServiceA).build()

        self.assertTrue(isinstance(s1, ServiceA))
        self.assertTrue(s1 == s2)
        self.assertTrue(s1 != s3)

class TestDependencyConfig(EasyDiTest):
    def test(self):
        self._container.register(ServiceB, DependencyConfig("section1.key1", None))

        self.assertTrue(isinstance(self._config, Config))
        self.assertTrue(self._config.get("section1.key1") == "1")
        self.assertTrue(self._config.get("section1.key3", "3") == "3")
        self.assertTrue(self._config.get("section1.key1", value_format=int) == 1)
 
        s1 = self.retrieve_instance(ServiceB).instance()
        self.assertTrue(isinstance(s1, ServiceB))
        self.assertTrue(s1.get() == "1")

class TestDependencyPath(EasyDiTest):
    def test(self):
        self._container.register(ProviderA, DependencyConfig("section1.key2"))
        self._container.register(ServiceA, DependencyPath("test.test_container.ProviderA"))
        
        s1 = self.retrieve_instance(ServiceA).instance()
        self.assertTrue(isinstance(s1, ServiceA))

class TestDependencyCallback(EasyDiTest):
    def test(self):
        # Test not registering ProviderB
        self._container.register(ServiceA, DependencyCallback(self.callback))
        self._container.register(ProviderA)
        
        s1 = self.retrieve_instance(ServiceA).instance()
        self.assertTrue(isinstance(s1, ServiceA))  
        self.assertTrue(isinstance(s1.provider, ProviderA))
        self.assertTrue(s1.provider.value == "A.2")

        # Update config and check if instance change 
        self._config.set("section1", "key1", 2)
        s1 = self.retrieve_instance(ServiceA).instance()
        self.assertFalse(isinstance(s1.provider, ProviderB))

        # Check if new instance change
        s1 = self.retrieve_instance(ServiceA).build()
        self.assertTrue(isinstance(s1.provider, ProviderB))
        self.assertTrue(s1.provider.value == "B.test")

    def callback(self, container):
        config = container["_config"].instance()
        if config.get("section1.key1") == "1":
            return ProviderA(config.get("section1.key2"))
        else:
            return ProviderB(config.get("section1.key3", "test"))
 
class TestDependencyGroup(EasyDiTest):
    def test(self):
        self._container.register(ProviderA, DependencyConfig("section1.key2"), _group="providers")
        self._container.register(ProviderB, DependencyConfig("section1.key2"), _group="providers")

        self._container.register(ServiceC, DependencyGroup("providers"))

        s1 = self.retrieve_instance(ServiceC).instance()
        self.assertTrue((s1.has(ProviderA) and s1.has(ProviderB)))
