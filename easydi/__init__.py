import collections
import inspect
import sys
import logging
import traceback
from readerwriterlock import rwlock
from pprint import pprint

_THREADING_LOCK = rwlock.RWLockWrite()

def _retrieve_class_path(obj):
    if not inspect.isclass(obj):
        raise Exception("Object must be a class")
    paths = obj.__module__.split(".")
    paths.append(obj.__qualname__)

    return paths

class ObjectFactoryMap(dict):
    def __init__(self, *args, **kwargs):
        self.update(*args, **kwargs)

        for arg in args:
            if isinstance(arg, dict):
                for k, v in arg.items():
                    self[k] = v

        if kwargs:
            for k, v in kwargs.items():
                self[k] = v

    def __getitem__(self, key):
        with _THREADING_LOCK.gen_rlock():
            val = dict.__getitem__(self, key)
        return val

    def __getattr__(self, attr):
        return self.get(attr)

    def __setattr__(self, key, value):
        self.__setitem__(key, value)

    def __setitem__(self, key, value):
        with _THREADING_LOCK.gen_wlock():
            super(ObjectFactoryMap, self).__setitem__(key, value)
            self.__dict__.update({key: value})

    def __delattr__(self, item):
        self.__delitem__(item)

    def __delitem__(self, key):
        with _THREADING_LOCK.gen_wlock():
            super(ObjectFactoryMap, self).__delitem__(key)
            del self.__dict__[key]

class ObjectFactory:
    """
    ObjectFactory

    Init:
        f = ObjectFactory(class_object, *args, **kwargs)

    Special Keyword Arguments:
        _group  : For object grouping, retrieve using DependencyGroup during container registration
        _alias  : For object aliasing
        _config : To set object as config, will be pass to DependencyConfig

    To get an instance:
        f.instance(*args, **kwargs) => Return single instance
        f.build(*args, **kwargs) => Return new instance
        f(build=False, *args, **kwargs) => same as f.instance(*args, **kwargs)
        f(build=True, *args, **kwargs) => same as f.build(*args, **kwargs)
        f(*args, **kwargs) => same as f.instance(*args, **kwargs)

    *args, **kwargs will be merge with dependency_args and dependency_kwargs is passed during class object creation
    """
    def __init__(self, class_object, containers, *args, **kwargs):
        self.__class_object = class_object
        self.__containers = containers
        self.__dependency_args = args
        self.__dependency_kwargs = kwargs
        self.__instance = None
        self._logger = logging.getLogger("easydi.{}".format(self.__class__.__name__))

    @property
    def name(self):
        return self.__class_object.__qualname__

    def update_containers(self, containers):
        self.__containers = containers

    def __create_instance(self, *args, **kwargs):

        dependency_args = [arg.build(self.__containers)
                           for arg in self.__dependency_args]
        dependency_kwargs = dict((k, v.build(self.__containers))
                                 for k, v in self.__dependency_kwargs.items())

        dependency_args = tuple(dependency_args) + tuple(args)
        dependency_kwargs.update(kwargs)
        try:
            return self.__class_object(*dependency_args, **dependency_kwargs)
        except:
            self._logger.debug("{} {}".format(self.__class_object, sys.exc_info()))
            raise Exception("Unable to create {} instance.".format(
                self.__class_object))

    def instance(self, *args, **kwargs):
        if self.__instance is None:
            instance = self.__create_instance(*args, **kwargs)
            self.__instance = instance
        return self.__instance

    def build(self, *args, **kwargs):
        return self.__create_instance(*args, **kwargs)

    def __call__(self, _build=False, *args, **kwargs):
        if _build is True:
            self._logger.debug([self.name, "Build"])
            return self.build(*args, **kwargs)
        else:
            return self.instance(*args, **kwargs)


class Dependency:
    """
    Dependency

    Default Dependency Object, return instance, list, dict or tuple
    """

    def __init__(self, _class, _single_instance=True, *args, **kwargs):
        self.__class = _class
        self.__single_instance = _single_instance
        self.__dependency_args = args
        self.__dependency_kwargs = kwargs
        self._logger = logging.getLogger("easydi.{}".format(self.__class__.__name__))

    def build(self, containers):
        obj = None

        if inspect.isclass(self.__class):
            try:
                class_path = _retrieve_class_path(self.__class)
                for path in class_path:
                    if isinstance(obj, ObjectFactoryMap):
                        obj = getattr(obj, path)
                    else:
                        obj = getattr(containers, path)

                # Unregister dependency return normal class ( always new instance )
                if obj is None:
                    return self.__class(*self.__dependency_args, **self.__dependency_kwargs)

                if self.__single_instance is False:
                    return obj.build(*self.__dependency_args, **self.__dependency_kwargs)
                return obj.instance(*self.__dependency_args, **self.__dependency_kwargs)
            except:
                self._logger.debug(sys.exc_info())
                raise Exception(
                    "Object {} is not register in containers".format(".".join(class_path)))
        elif isinstance(self.__class, (list, dict, tuple, int, float)):
            # Tuple, List, Dict, etc
            return self.__class

        raise Exception("Unsupported object type")

class DependencyPath:
    def __init__(self, _path, _single_instance=True, *args, **kwargs):
        self.__path = _path
        self.__single_instance = _single_instance
        self.__dependency_args = args
        self.__dependency_kwargs = kwargs
        self._logger = logging.getLogger("easydi.{}".format(self.__class__.__name__))

    def build(self, containers):
        obj = None

        try:
            class_path = self.__path.split(".")

            for path in class_path:
                if isinstance(obj, ObjectFactoryMap):
                    obj = getattr(obj, path)
                else:
                    obj = getattr(containers, path)

            # Unregister dependency return normal class ( always new instance )
            if obj is None:
                return self.__class(*self.__dependency_args, **self.__dependency_kwargs)

            if self.__single_instance is False:
                return obj.build(*self.__dependency_args, **self.__dependency_kwargs)
            return obj.instance(*self.__dependency_args, **self.__dependency_kwargs)
        except:
            self._logger.debug(sys.exc_info())
            raise Exception(
                "Object {} is not register in containers".format(".".join(class_path)))

        raise Exception("Unsupported object type")

class DependencyConfig:
    """
    Dependency Config

    Get config value from specified config object
    First register config object to container using _config=True keyword argument
    Then register an object that require to read config to container with this class as dependency

    Arguments:
        config_path : config path with dot, we assume config is in dict
        placeholder : default value when config is not found
        value_format : Config value return format in str, bool, int, float default to str
    """
    def __init__(self, config_path, placeholder=None, value_format=str):
        self.__config_path = config_path
        self.__placeholder = placeholder
        self.__value_format = value_format
        self._logger = logging.getLogger("easydi.{}".format(self.__class__.__name__))

    def build(self, containers):
        try:
            config_instance = containers["_config"].instance()
        except:
            raise Exception("Object for config not set, please register object with _config=True")

        get_function = getattr(config_instance, "get", None)
        if not callable(get_function):
            raise Exception("Config must implement : def get(config_path, placeholder, value_format)")

        return config_instance.get(self.__config_path, placeholder=self.__placeholder, value_format=self.__value_format)

class DependencyCallback:
    """
    Dependency Callback

    Run defined callback function
        callback(containers, *args, **kwargs)

    Arguments:
        callback : callable function
        _single_instance : return new instance if False
        args: callback function arguments
        kwargs: callback function keyword arguments
    """
    def __init__(self, callback, _single_instance=True, *args, **kwargs):
        self.__callback = callback
        self.__single_instance = _single_instance
        self.__dependency_args = args
        self.__dependency_kwargs = kwargs
        self._logger = logging.getLogger("easydi.{}".format(self.__class__.__name__))

    def build(self, containers):
        try:
            result =  self.__callback(containers, *self.__dependency_args, **self.__dependency_kwargs)

            if not inspect.isclass(result):
                return result

            class_path = _retrieve_class_path(result)
            obj = None

            for path in class_path:
                if isinstance(obj, ObjectFactoryMap):
                    obj = getattr(obj, path)
                else:
                    obj = getattr(containers, path)

            # Unregister dependency return normal class ( always new instance )
            if obj is None:
                return result(*self.__dependency_args, **self.__dependency_kwargs)

            if self.__single_instance is False:
                return obj.build(*self.__dependency_args, **self.__dependency_kwargs)
            return obj.instance(*self.__dependency_args, **self.__dependency_kwargs)
        except:
            raise Exception("Unsupported object type")

class DependencyGroup:
    """
    DependencyGroup

    Return list of ObjectFactory instance
    """

    def __init__(self, group_name, _single_instance=True, *args, **kwargs):
        self.__group_name = group_name
        self.__single_instance = _single_instance
        self.__dependency_args = args
        self.__dependency_kwargs = kwargs
        self._logger = logging.getLogger("easydi.{}".format(self.__class__.__name__))

    def build(self, containers):
        objs = []

        if  self.__group_name not in containers["_group"]:
            return objs

        for obj in containers["_group"][self.__group_name]:
            try:
                if self.__single_instance is False:
                    objs.append(obj.build(*self.__dependency_args,
                                          **self.__dependency_kwargs))
                else:
                    objs.append(obj.instance(*self.__dependency_args,
                                         **self.__dependency_kwargs))
            except:
                self._logger.debug(sys.exc_info())

        return objs

class Container:
    """
    Container of all object, should be called only once in application
    Might not thread safe
    """
    def __init__(self):
        self.__container = ObjectFactoryMap(
            {"_group": ObjectFactoryMap(), "_alias": ObjectFactoryMap(), "_config": None})

    def __getattr__(self, key):
        try:
            return self.__container.get(key)
        except:
            try:
                return self.__container._alias.get(key)
            except:
                pass
            raise Exception("Dependency {} is not register".format(key))

    def update(self, container):
        if not isinstance(container, Container):
            raise Exception("Can only update form Container instance")

        self._update_containers(self.__container, container.list())

        for obj in self.list_object_factories():
            obj.update_containers(self.__container)

    def _update_containers(self, dict1, dict2):
        for key, val in dict2.items():
            if key in dict1:
                if isinstance(dict1[key], ObjectFactoryMap):
                    self._update_containers(dict1[key], val)
                elif isinstance(dict1[key], ObjectFactory):
                    if val is not None:
                        dict1[key] = val
                elif isinstance(dict1[key], list) and isinstance(val, list):
                    dict1[key] += val
                else:
                    dict1[key].update(val)
            else:
                dict1[key] = val

    def list_object_factories(self, objects=None):
        objs = []

        objects = objects or self.__container

        for k, v in objects.items():
            if isinstance(v, dict):
                if k in ["_group", "_alias", "_config"]:
                    continue

                objs += self.list_object_factories(v)
            else:
                objs.append(v)
        return objs

    def list(self):
        return self.__container

    def register(self, class_object, *args, **kwargs):
        # Change class_object to Dependency object by default
        args = [(Dependency(arg) if not isinstance(
            arg, (Dependency, DependencyPath, DependencyGroup, DependencyConfig, DependencyCallback)) else arg) for arg in args]

        object_group = kwargs.pop("_group", None)
        object_alias = kwargs.pop("_alias", None)
        object_config = kwargs.pop("_config", False)

        kwargs = dict((k, Dependency(v) if not isinstance(
            v, (Dependency, DependencyPath, DependencyGroup, DependencyConfig)) else v) for k, v in kwargs.items())

        obj = ObjectFactory(class_object, self.__container, *args, **kwargs)
        self.__group_factory(obj, object_group)
        self.__add_alias(obj, object_alias)
        self.__set_config(obj, object_config)

        paths = _retrieve_class_path(class_object)
        current_level = self.__container

        for i, path in enumerate(paths):
            if (i == len(paths) - 1):
                current_level[path] = obj
            else:
                if path not in current_level:
                    current_level[path] = ObjectFactoryMap()
            current_level = current_level[path]

    def __set_config(self, obj, as_config=True):
        if as_config:
            self.__container["_config"] = obj

    def __add_alias(self, obj, alias_name=None):
        if alias_name is None:
            return False

        self.__container._alias[alias_name] = obj

    def __group_factory(self, obj, group_name=None):
        if group_name is None:
            return False

        if group_name not in self.__container._group:
            self.__container._group[group_name] = []

        self.__container._group[group_name].append(obj)
