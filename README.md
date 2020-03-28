# EasyDI

Python Dependency Configuration ( Injection ) Library

## Installation

```bash
pip3 install easydi
```

## Usage
Assume you have this project structure
```bash
my_project
|- my_project
    |- __init__.py
    |- my_module.py
    |- config.py
    |- dependency.py
    |- __main__.py
|- setup.py
```

Create a config class in config.py
```python
# Config must implement below method
class MyConfig:
    def get(self, name, placeholder, value_format):
        return value
```

Create dependency.py
```python
# Import all your module
from my_project.my_module import *
from my_project.config import MyConfig

from easydi import *

container = Container()

container.register(MyConfig, _config=True)
container.register(MyClass, DependencyConfig("my.config", "placeholder"))
...
```

Use in your \__main\__.py
```python
from dependency import container

def main():
    # Init config instance before using other class
    config = container.my_project.MyConfig.instance()

    # Run your application
    your_class = container.my_project.MyClass.instance()
    your_class.run()

if __name__ == "__main__":
    main()
```

## Container

#### Format to registering an object to a container is:
```bash
( <object>, *<dependency object>, <_config|_group|_alias> )
```
- **object** : class object, not initiate
- **dependency object** (optional) : see Dependency Object
- **_config**  (optional) : mark object as config, there can be only one object. must implement * **get(name, placeholder, value_format)** * method. Will be use by **DependencyConfig**
- **_group** (optional) : mark object as specific group. Will be use by **DependencyGroup**
- **_alias** (optional) : give an alias name to an object

Container can be merge with other container if required, note that same path will be overwritten
```
containerA = Container()
containerB = Container()
containerA.update(containerB)
```

#### Retrieving instance from container

When retrieving from container you will be given an **ObjectFactory**, this is a wrapper for your object. To retrieve your object you can use one of this method ( assuming **f** is the **ObjectFactory** ) :
- f.instance(*args, **kwargs) : Return single instance
- f.build(*args, **kwargs) : Return new instance
- f(_build=False, *args, **kwargs) : same as f.instance(*args, **kwargs)
- f(_build=True, *args, **kwargs) : same as f.build(*args, **kwargs)
- f(*args, **kwargs) : same as f.instance(*args, **kwargs)

Passing additional arguments or keyword arguments is possible when using **instance()** ( first time only ) or **build()**

## Dependency Object

- **Dependency** : Default type if nothing is specified
- **DependencyConfig** : To retrieve value from user defined config
- **DependencyPath** : Retrieve object by it's full path
- **DependencyCallback** : Return object from a custom function
- **DependencyGroup** : Pass multiple registered object as list
