# qt-opengl-compatibility

Checks which versions of OpenGL contexts can be created with PyQt and PySide and
whether you can create those contexts using Qt's abstractions for OpenGL or if you
need to use PyOpenGL.

Between 4 versions of Python bindings of Qt (PySide2, PySide6, PyQt5, PyQt6), 10
versions of OpenGL API to be tested (3.0 - 3.3, 4.0 - 4.5) and the choice of
PyOpenGL vs Qt's API for OpenGL, there are a total of 80 scenarios to be tested.
To automate this, `tox` is used as described below.

## Requirements

In your virtual environment,

```shell
pip install tox
```

## Usage

The `tox` environments are named as follows:

```
# Python3.9 - Qt binding to use - Qt/PyOpenGL - GL major version - GL minor version
py39-{PyQt5,PyQt6,PySide2,PySide6}-gl{qt,py}-glmaj{3,4}-glmin{0,1,2,3,4,5}
```

To run different scenarios:

```sh
# to test all possible scenarios
tox
# to test only PyQt5 with Qt's GL API for OpenGL 3.0 - 3.3
tox -e 'py39-PyQt5-glqt-glmaj3-glmin{0,1,2,3}'
```

The script `check.py` tries to draw a triangle in OpenGL. The resulting window
on successful execution looks like this:

![image](https://user-images.githubusercontent.com/10922171/125040016-fc993480-e04b-11eb-8570-49dd186966ce.png)

To mark the execution successful, press 'Yes'. If there are problems (most likely a black screen), then
it's possibly an issue with the binding not able to get OpenGL functions, so you should press 'No' to
mark the execution as a failure.

The tox environments mentioned above install relevant dependencies for `check.py` to run
and set appropriate environment variables automatically. These are provided here for
documentation, but you wouldn't need to set them explicitly unless you're running
`check.py` without `tox`.

```
# Major version of OpenGL API to test
# Can be 3 or 4
TEST_GL_MAJOR_VER

# Minor version of OpenGL API to test
# If major version is 3, it can be 0-3
# If major version is 4, it can be 0-5
TEST_GL_MINOR_VER

# The binding against which OpenGL API support is to be tested
# Valid values are 'qt' and 'pyside'
TEST_QT_BINDING

# Whether to use native OpenGL API using PyOpenGL or use Qt's abstractions for OpenGL
# Corresponding values are 'pyopengl' and 'qt'
TEST_OPENGL_API
```

## Notes on results

The following holds after testing on NVidia GTX1070 with the caveat that "doesn't work" may be because of a bug in my code or that I don't know of a way to make it work yet:

- PyQt5 and PyQt6 don't work with Qt's OpenGL wrappers (`versionFunctions()` and the like).
- PyQt5 and PyQt6 work with PyOpenGL, so that may be the only option.
- PySide2 doesn't work with Qt's OpenGL wrappers, but does work with PyOpenGL.
- PySide6 works with both Qt's OpenGL wrappers and PyOpenGL.
  - Qt's OpenGL wrappers don't come with OpenGL constants. So, you either need to add those in manually or use PyOpenGL for just the constant values.
  - If a function bound by Qt's versionFunctions() needs a void pointer (e.g. `glVertexAttribPointer`), you must use `VoidPtr` class defined by `shiboken` package (comes with PySide). In contrast, PyOpenGL's wrapper for `glVertexAttribPointer` prefers `ctypes.c_void_p` (you can also use PyOpenGL's alias `GLvoidp`).
