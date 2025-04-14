from FreeCAD import Base
from BOPTools import BOPFeatures
from PySide import QtGui
import Draft
import importSVG
import Mesh
import os
import Part
import time


SVG_PREFIX = "Alufo"
MODEL_NAME = "AlufoMiddle"
SIDES = [ "Left", "Right" ]
HAS_GUI = ("Gui" in dir())
INDENT = 0
TIMERS = {}
VERBOSE_SVG_IMPORT = False

DOC = App.newDocument(MODEL_NAME)

svgDir = ""

# KiCad SVG export to 3D model component mapping:
#     Layer Name | Height | Is Outline
#     ---------- | ------ | ----------
LAYERS = [
    [ "Edge_Cuts", 3.5,     True  ],
    [ "User_2",    1.0,     False ],
    [ "User_3",    1.8,     False ],
    [ "User_4",    2.2,     False ],
    [ "User_5",    2.2,     True  ],
    [ "User_9",    4.0,     False ],
]


def log(message):
    App.Console.PrintMessage(message + "\n")

def logStart(message):
    global TIMERS
    global INDENT
    if INDENT == 0:
        log("")
    log(f"{' ' * INDENT} Starting {message}…")
    TIMERS[message] = time.time()
    INDENT += 2

def logEnd(message):
    global INDENT
    INDENT -= 2
    log(f"{(' ' * INDENT)}…finished {message} ({getElapsedTime(message)}).")

def logUnexpected(message, originalMessage):
    global TIMERS
    global INDENT
    TIMERS.pop(originalMessage)
    INDENT -= 2
    logWarning((' ' * INDENT) + message)

def getElapsedTime(message):
    global TIMERS
    t = time.time()-TIMERS.pop(message)
    if t < 0.001:
        t *= 1000000
        u = "µs"
    else:
        u = "s"
    return f"{t:.03f}{u}"

def logError(message):
    App.Console.PrintError(message + '\n')

def logWarning(message):
    App.Console.PrintWarning(message + '\n')

def _d(message):
    log(message)


def getSvgDirectory():
    global svgDir

    if HAS_GUI:
        svgDir = QtGui.QFileDialog.getExistingDirectory(caption="SVG Parent Directory")
    else:
        svgDir = input("Enter SVG directory: ").strip("\"' ").replace("\\", "")
        #svgDir = "Exports"

    if not svgDir:
        logError("No directory specified — stopping")
        return False

    return svgDir


def getSvgFilename(side, layer):

    return os.path.join(svgDir, SVG_PREFIX + side + '-' + layer + ".svg")


def extrudePath(parent, path, height):

    extrusion = parent.addObject("Part::Extrusion")
    extrusion.Base = path
    extrusion.Dir = (0, 0, height)
    extrusion.Solid = True

    return extrusion

def hideObject(obj):
    if hasattr(obj, "ViewObject") and hasattr(obj.ViewObject, "Visibility"):
        obj.ViewObject.Visibility = False


def generateLayer(side, layerName, layerHeight, layerIsOutline):

    action = f"generation of {side}.{layerName} layer"
    logStart(action)

    svg = getSvgFilename(side, layerName)
    if not os.path.isfile(svg):
        logUnexpected(f"…no SVG file for {side} {layerName} found - skipping layer", action)
        return None

    newObjectStart = len(DOC.Objects)

    # Import SVG:
    logStart(f"loading file '{svg}'")
    App.Console.SetStatus("Console", "Msg", VERBOSE_SVG_IMPORT)
    importSVG.insert(svg, DOC.Name)
    App.Console.SetStatus("Console", "Msg", True)
    logEnd(f"loading file '{svg}'")

    if layerIsOutline:
        # This layer is a set of paths forming an outline (e.g., edge cuts) and not a
        # collection of distinct shapes. Combine all the paths into a sketch:
        sketch = Draft.makeSketch(DOC.Objects[newObjectStart:], autoconstraints=True)

        # Remove the component paths leaving only the sketch:
        for obj in DOC.Objects[newObjectStart:]:
            if obj != sketch:
                DOC.removeObject(obj.Name)

    # Loop through all the new objects (for outline layers only be the sketch will be
    # remaining) and extrude them:
    extrusions = []
    for obj in DOC.Objects[newObjectStart:]:
        extrusions.append(extrudePath(DOC, obj, layerHeight))
        hideObject(obj)

    # If there is only one extrusion then that is the layer,
    # otherwise combine all the parts into a single fusion object:
    if len(extrusions) == 1:
        layer = extrusions[0]
        layer.Label = side + layerName
    elif len(extrusions) > 1:
        logStart(f"fusion of {side}.{layerName} layer")
        layer = DOC.addObject("Part::MultiFuse", side + layerName)
        layer.Shapes = extrusions
        logEnd(f"fusion of {side}.{layerName} layer")

    logEnd(action)

    return layer


def generateSide(side):

    action = f"generation of {side} side"
    logStart(action)

    bop = BOPFeatures.BOPFeatures(DOC)
    body = None

    for layer in LAYERS:
        if obj := generateLayer(side, *layer):
            if body:
                prevLabel = body.Label
                logStart(f"subtraction of {obj.Label} from {prevLabel}")
                body = bop.make_cut([body.Name, obj.Name])
                logEnd(f"subtraction of {obj.Label} from {prevLabel}")
                body.Label = prevLabel + "-" + obj.Label.replace(side, "")
            else:
                body = obj

    # Flip over final body so that cuts are on top in both FreeCAD and the exported STL:
    body.Placement = App.Placement(App.Vector(0,0,0), App.Rotation(App.Vector(0,1,0),180))

    logStart(f"recompute of {side} side")
    x = DOC.recompute()
    logEnd(f"recompute of {side} side")

    stl = os.path.join(svgDir, MODEL_NAME + side + ".stl")
    logStart(f"writing {side} body to '{stl}'")
    Mesh.export([body], stl)
    logEnd(f"writing {side} body to '{stl}'")

    logEnd(action)


def resetView():
    if HAS_GUI:
        Gui.SendMsgToActiveView("ViewFit")


def makeMiddle():

    if getSvgDirectory():

        for side in SIDES:
            generateSide(side)

        resetView()

    else:
        App.closeDocument(DOC.Name)


makeMiddle()
