from textwrap import dedent
from enum import Enum
from typing import Tuple
import sys
import os

# Conditional imports
# Qt binding
_qt_binding = os.getenv('TEST_QT_BINDING')
if _qt_binding is None:
    raise RuntimeError(
        'Set the Qt binding to use with TEST_QT_BINDING = { pyqt5, pyqt6, pyside2, pyside6 }')
# Prepare for comparisons
_qt_binding = _qt_binding.strip().lower()

if _qt_binding == 'pyside2':
    from PySide2 import QtCore as qtc
    from PySide2.QtWidgets import QOpenGLWidget
    from PySide2 import QtGui as qtg
    from PySide2.QtGui import (QOpenGLBuffer, QOpenGLShader,
                                QOpenGLShaderProgram, QOpenGLVersionProfile,
                                QOpenGLVertexArrayObject)
    from PySide2 import QtWidgets as qtw
    from shiboken2 import VoidPtr
    # Need array for sending vertex data as bytes
    # You may also consider numpy if you need to do operations on array
    import array
elif _qt_binding == 'pyqt5':
    from PyQt5 import QtCore as qtc
    from PyQt5.QtWidgets import QOpenGLWidget
    from PyQt5 import QtGui as qtg
    from PyQt5.QtGui import (QOpenGLBuffer, QOpenGLShader,
                            QOpenGLShaderProgram, QOpenGLVersionProfile,
                            QOpenGLVertexArrayObject)
    from PyQt5 import QtWidgets as qtw
    from ctypes import c_void_p as VoidPtr
    # Need array for sending vertex data as bytes
    # You may also consider numpy if you need to do operations on array
    import array
elif _qt_binding == 'pyside6':
    from PySide6 import QtCore as qtc
    from PySide6.QtOpenGLWidgets import QOpenGLWidget
    from PySide6 import QtGui as qtg
    from PySide6.QtOpenGL import (QOpenGLBuffer, QOpenGLShader,
                                  QOpenGLVersionFunctionsFactory,
                                  QOpenGLShaderProgram, QOpenGLVersionProfile,
                                  QOpenGLVertexArrayObject)
    from PySide6 import QtWidgets as qtw
    from shiboken6 import VoidPtr
    # Need array for sending vertex data as bytes
    # You may also consider numpy if you need to do operations on array
    import array
elif _qt_binding == 'pyqt6':
    from PyQt6 import QtCore as qtc
    from PyQt6.QtOpenGLWidgets import QOpenGLWidget
    from PyQt6 import QtGui as qtg
    from PyQt6.QtOpenGL import (QOpenGLBuffer, QOpenGLShader,
                                QOpenGLVersionFunctionsFactory,
                                QOpenGLShaderProgram, QOpenGLVersionProfile,
                                QOpenGLVertexArrayObject)
    from PyQt6 import QtWidgets as qtw
    # Need array for sending vertex data as bytes
    # You may also consider numpy if you need to do operations on array
    import array
else:
    raise RuntimeError(f'Invalid value for TEST_QT_BINDING: {_qt_binding}')

_gl_api = os.getenv('TEST_OPENGL_API')
if _gl_api is None:
    raise RuntimeError('Set the OpenGL API to use with TEST_OPENGL_API to { qt, pyopengl }')

_gl_api = _gl_api.strip().lower()

if _gl_api == 'pyopengl':
    from OpenGL import GL
    # Need ctypes to create C-type arrays
    import ctypes
elif _gl_api == 'qt':
    # Only needed for figuring out size of float
    # Could use value 4 too
    import ctypes
else:
    raise RuntimeError(f'Invalid value for TEST_OPENGL_API: {_gl_api}')

class OpenGLAPI(Enum):
    QT = 0,
    PYOPENGL = 1

def glsl_version_mapper():
    glsl_version_mapping = {
        (2, 0): (1, 10),
        (2, 1): (1, 20),
        (3, 0): (1, 30),
        (3, 1): (1, 40),
        (3, 2): (1, 50),
    }

    def mapper(version: Tuple[int]) -> Tuple[int]:
        if version in glsl_version_mapping:
            glsl_version = glsl_version_mapping[version]
        elif version[0] == 3 and version[1] == 3 or version[0] == 4 and 0 <= version[1] <= 6:
            glsl_version = (version[0], version[1] * 10)
        else:
            raise ValueError(f"Invalid OpenGL version: {version}")
        return glsl_version

    return mapper


class TriangleWidget(QOpenGLWidget):
    def __init__(self, parent=None,
                       version_profile: QOpenGLVersionProfile=QOpenGLVersionProfile(),
                       api=OpenGLAPI.QT):
        super().__init__(parent)
        self._req_version_profile = version_profile
        self._api = api

        fmt = qtg.QSurfaceFormat()
        fmt.setRenderableType(qtg.QSurfaceFormat.RenderableType.OpenGL)
        fmt.setVersion(*self._req_version_profile.version())
        fmt.setProfile(self._req_version_profile.profile())
        self.setFormat(fmt)

        self._gl = None

        self._vertices = [
            #  x     y    z    r    g    b
             0.0,  0.5, 0.0, 1.0, 0.0, 0.0,
            -0.5, -0.5, 0.0, 0.0, 1.0, 0.0,
             0.5, -0.5, 0.0, 0.0, 0.0, 1.0
        ]

        # Get GLSL version string for the given OpenGL version
        glsl_mapper = glsl_version_mapper()
        glsl_ver = glsl_mapper(self._req_version_profile.version())
        glsl_ver_str = "{}{:<02d}".format(*glsl_ver)

        self._vs = dedent("""
        #version {glsl_ver_str}

        in vec3 posIn;
        in vec3 colorIn;

        out vec3 color;

        void main() {{
            color = colorIn;
            gl_Position = vec4(posIn, 1.0);
        }}
        """.format(glsl_ver_str=glsl_ver_str))

        self._fs = dedent("""
        #version {glsl_ver_str}

        in vec3 color;

        out vec4 fragColor;

        void main() {{
            fragColor = vec4(color, 1.0);
        }}
        """.format(glsl_ver_str=glsl_ver_str))

        self._init()

    def _init(self):
        if self._api == OpenGLAPI.QT:
            self._init_qt()
        elif self._api == OpenGLAPI.PYOPENGL:
            self._init_pyopengl()

    def _init_qt(self):
        self._program = QOpenGLShaderProgram()
        self._vao = QOpenGLVertexArrayObject()
        self._vtx_buffer = QOpenGLBuffer(QOpenGLBuffer.Type.VertexBuffer)
        self._vtx_buffer.setUsagePattern(QOpenGLBuffer.UsagePattern.StaticDraw)

    def _init_pyopengl(self):
        # Defer OpenGL API calls to initializeGL() as the context is
        # automatically made current before initializeGL() is called
        pass

    def initializeGL(self):
        """Set up any required OpenGL resources and state

        Called once before the first time resizeGL() or paintGL() is called.
        The rendering context has already been made current before this
        function is called. Note however that the framebuffer is not yet
        available at this stage, so avoid issuing draw calls from here. Defer
         such calls to paintGL() instead.
        """
        self.context().aboutToBeDestroyed.connect(self._cleanup)

        if self._api == OpenGLAPI.QT:
            self._initializeGL_qt()
        elif self._api == OpenGLAPI.PYOPENGL:
            self._initializeGL_pyopengl()

        self._compile_gl()
        self._gl.glClearColor(0.2, 0.3, 0.0, 1.0)


    def _initializeGL_qt(self):
        if _qt_binding in ['pyside6', 'pyqt6']:
            # This is PyQt6/PySide6 way of doing things
            self._gl = QOpenGLVersionFunctionsFactory.get(self._req_version_profile, self.context())
        else:
            # This is PyQt5/PySide2 way of doing things
            self._gl = self.context().versionFunctions()

        if self._gl is None:
            qtc.qFatal("Missing OpenGL")

        # GL constants manually set
        self._gl.GL_COLOR_BUFFER_BIT = 0x00004000
        self._gl.GL_TRIANGLES = 0x0004
        self._gl.GL_FLOAT = 0x1406
        self._gl.GL_FALSE = 0

        self._vao.create()
        self._vao.bind()

        self._vtx_buffer.create()

        vtxData = array.array('f', self._vertices)

        self._vtx_buffer.bind()
        self._vtx_buffer.allocate(vtxData, len(vtxData) * vtxData.itemsize)

        float_size = ctypes.sizeof(ctypes.c_float)

        self._gl.glVertexAttribPointer(0, 3, self._gl.GL_FLOAT, self._gl.GL_FALSE, 6 * float_size, VoidPtr(0))
        self._gl.glVertexAttribPointer(1, 3, self._gl.GL_FLOAT, self._gl.GL_FALSE, 6 * float_size, VoidPtr(3 * float_size))
        self._gl.glEnableVertexAttribArray(0)
        self._gl.glEnableVertexAttribArray(1)

        self._vao.release()


    def _initializeGL_pyopengl(self):
        self._gl = GL
        # We get constants for free via PyOpenGL
        self._vao = self._gl.glGenVertexArrays(1)
        self._gl.glBindVertexArray(self._vao)

        self._vtx_buffer = self._gl.glGenBuffers(1)
        self._gl.glBindBuffer(self._gl.GL_ARRAY_BUFFER, self._vtx_buffer)

        vtxData = (ctypes.c_float * len(self._vertices))(*self._vertices)

        self._gl.glBufferData(self._gl.GL_ARRAY_BUFFER, self._gl.sizeof(vtxData), vtxData, self._gl.GL_STATIC_DRAW)

        float_size = self._gl.sizeof(self._gl.GLfloat)

        self._gl.glVertexAttribPointer(0, 3, self._gl.GL_FLOAT, self._gl.GL_FALSE, 6 * float_size, self._gl.GLvoidp(0))
        self._gl.glVertexAttribPointer(1, 3, self._gl.GL_FLOAT, self._gl.GL_FALSE, 6 * float_size, self._gl.GLvoidp(3 * float_size))
        self._gl.glEnableVertexAttribArray(0)
        self._gl.glEnableVertexAttribArray(1)


    def _compile_gl(self):
        if self._api == OpenGLAPI.QT:
            self._compile_gl_qt()
        elif self._api == OpenGLAPI.PYOPENGL:
            self._compile_gl_pyopengl()


    def _compile_gl_qt(self):
        self._program.addShaderFromSourceCode(QOpenGLShader.ShaderTypeBit.Vertex, self._vs)
        self._program.addShaderFromSourceCode(QOpenGLShader.ShaderTypeBit.Fragment, self._fs)
        self._program.bindAttributeLocation("posIn", 0)
        self._program.bindAttributeLocation("colorIn", 1)
        self._program.link()

    def _compile_gl_pyopengl(self):
        vertexShader = self._gl.glCreateShader(self._gl.GL_VERTEX_SHADER)
        self._gl.glShaderSource(vertexShader, self._vs.encode('utf-8'))
        self._gl.glCompileShader(vertexShader)

        fragmentShader = self._gl.glCreateShader(self._gl.GL_FRAGMENT_SHADER)
        self._gl.glShaderSource(fragmentShader, self._fs.encode('utf-8'))
        self._gl.glCompileShader(fragmentShader)

        self._program = self._gl.glCreateProgram()
        self._gl.glAttachShader(self._program, vertexShader)
        self._gl.glAttachShader(self._program, fragmentShader)

        self._gl.glBindAttribLocation(self._program, 0, "posIn")
        self._gl.glBindAttribLocation(self._program, 1, "colorIn")

        self._gl.glLinkProgram(self._program)

        self._gl.glDeleteShader(vertexShader)
        self._gl.glDeleteShader(fragmentShader)



    def paintGL(self):
        """Paint the scene using OpenGL functions

        The rendering context has already been made current before this
        function is called. The framebuffer is also bound and the viewport is
        set up by a call to glViewport()
        """
        if self._api == OpenGLAPI.QT:
            self._paintGL_qt()
        elif self._api == OpenGLAPI.PYOPENGL:
            self._paintGL_pyopengl()

    def _paintGL_qt(self):
        self._gl.glClear(self._gl.GL_COLOR_BUFFER_BIT)
        self._program.bind()
        self._vao.bind()
        self._gl.glDrawArrays(self._gl.GL_TRIANGLES, 0, 3)
        self._program.release()
        self._vao.release()

    def _paintGL_pyopengl(self):
        self._gl.glClear(self._gl.GL_COLOR_BUFFER_BIT)
        self._gl.glUseProgram(self._program)
        self._gl.glBindVertexArray(self._vao)
        self._gl.glDrawArrays(self._gl.GL_TRIANGLES, 0, 3)

    def resizeGL(self, width: int, height: int):
        """Called whenever the widget has been resized

        The rendering context has already been made current before this
        function is called. The framebuffer is also bound.
        """
        self._gl.glViewport(0, 0, width, height)

    def _cleanup(self):
        if self._api == OpenGLAPI.QT:
            self._cleanup_qt()
        elif self._api == OpenGLAPI.PYOPENGL:
            self._cleanup_pyopengl()

    def _cleanup_qt(self):
        self.makeCurrent()
        self._vtx_buffer.destroy()
        del self._program
        self._program = None
        self.doneCurrent()

    def _cleanup_pyopengl(self):
        self.makeCurrent()
        self._gl.glDeleteVertexArrays(1, self._vao)
        self._gl.glDeleteBuffers(1, self._vtx_buffer)
        self._gl.glDeleteProgram(self._program)
        self.doneCurrent()


class Window(qtw.QWidget):
    def __init__(self, parent=None, version_profile: QOpenGLVersionProfile=QOpenGLVersionProfile(), api=OpenGLAPI.QT):
        super().__init__(parent)
        self.setGeometry(0, 0, 640, 480)
        self.setLayout(qtw.QVBoxLayout())
        self.triangleWgt = TriangleWidget(self, version_profile=version_profile, api=api)
        self.layout().addWidget(self.triangleWgt)
        self.layout_bottom = qtw.QHBoxLayout()
        self.layout().addLayout(self.layout_bottom)
        self.yes_button = qtw.QPushButton(text='Yes')
        self.no_button = qtw.QPushButton(text='No')
        self.layout_bottom.addWidget(self.yes_button)
        self.layout_bottom.addWidget(self.no_button)

        self.yes_button.clicked.connect(self.on_yes)
        self.no_button.clicked.connect(self.on_no)

    def on_yes(self):
        app.quit()

    def on_no(self):
        app.exit(1)

if __name__ == '__main__':
    gl_major = int(os.getenv('TEST_GL_MAJOR_VER'))
    gl_minor = int(os.getenv('TEST_GL_MINOR_VER'))

    version_profile = QOpenGLVersionProfile()
    version_profile.setVersion(gl_major, gl_minor)
    version_profile.setProfile(qtg.QSurfaceFormat.OpenGLContextProfile.CoreProfile)

    app = qtw.QApplication(sys.argv)

    if _gl_api == 'qt':
        api = OpenGLAPI.QT
    elif _gl_api == 'pyopengl':
        api = OpenGLAPI.PYOPENGL

    wdw = Window(version_profile=version_profile, api=api)
    wdw.show()
    sys.exit(app.exec() if hasattr(app, 'exec') else app.exec_())
