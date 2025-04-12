from FreeCAD import Base
from BOPTools import BOPFeatures
from PySide import QtGui
import Draft
import importSVG
import Mesh
import os
import Part


SVG_PREFIX = "Alufo-"
MODEL_NAME = "AlufoMiddle"
SIDE_DIRS = [ "Left", "Right" ]

svgParentDir = ""

# KiCad SVG export to 3D model component mapping:
#     Layer Name | Height | Is Outline
#     ---------- | ------ | ----------
LAYERS = [
    [ "Edge_Cuts", 3.5,     True  ],
    [ "User_2",    1.0,     False ],
    [ "User_3",    1.8,     False ],
    [ "User_4",    2.2,     False ],
    [ "User_5",    2.2,     True  ],
    [ "User_9",    4.0,     False ]
]

def getSvgParentDirectory():

    #directory = QtGui.QFileDialog.getExistingDirectory(caption="SVG Parent Directory")
    directory = "/Users/barnaby/Development/GitHub/Alufo/Middle Layer"
    if not directory:
        print("*** No directory specified — stopping")
        return False
    else:
        for side in SIDE_DIRS:
            if not os.path.isdir(os.path.join(directory, side)):
                print(f"*** Directory {svgParentDir} does not contain a directory {side} — stopping")
                return False

    return directory


def extrudePath(parent, path, height):

    extrusion = parent.addObject("Part::Extrusion")
    extrusion.Base = path
    extrusion.Dir = (0, 0, height)
    extrusion.Solid = (True)

    return extrusion.Name

def hideObject(obj):
    obj.ViewObject.Visibility = False

def generateLayer(doc, side, layerName, layerHeight, layerIsOutline):

    extrusions = []

    svg = os.path.join(svgParentDir, side, SVG_PREFIX + layerName + ".svg")
    if not os.path.isfile(svg):
        print(f"*** No SVG file for {side} {layerName} found - skipping layer")
    else:
        newObjectStart = len(doc.Objects)

        # Import SVG:
        importSVG.insert(svg, doc.Name)

        if layerIsOutline:
            # This layer is a set of paths forming an outline (e.g., edge cuts) and not a
            # collection of distinct shapes. Combine all the paths into a sketch:
            sketch = Draft.makeSketch(doc.Objects[newObjectStart:], autoconstraints=True)

            # Remove the component paths leaving only the sketch:
            for obj in doc.Objects[newObjectStart:]:
                if obj != sketch:
                    doc.removeObject(obj.Name)

        # Loop through all the new objects (for outline layers only be the sketch will be
        # remaining) and extrude them:
        for obj in doc.Objects[newObjectStart:]:
            extrusions.append(extrudePath(doc, obj, layerHeight))
            hideObject(obj)

    return extrusions


def generateSide(doc, side):

    extrusions = []
    bop = BOPFeatures.BOPFeatures(doc)

    for layer in LAYERS:
        extrusions += generateLayer(doc, side, *layer)

    # Gather all the objects except the first (the body) into a single item:
    fusion = bop.make_multi_fuse(extrusions[1:])

    # Cut out all the other objects from the body:
    body = bop.make_cut([extrusions[0], fusion.Name])
    body.Label = MODEL_NAME + side

    # Recompute body and export as STL:
    x = doc.recompute()
    stl = os.path.join(svgParentDir, body.Label + ".stl")
    print(f"*** Writing {Side} body to {stl}")
    Mesh.export([body], stl)


def resetView():
    Gui.SendMsgToActiveView("ViewFit")
    # TODO: Rotate view 180º


def makeMiddle():
    global svgParentDir

    if svgParentDir := getSvgParentDirectory():

        doc = App.newDocument(MODEL_NAME)

        for side in SIDE_DIRS:
            generateSide(doc, side)

        resetView()


makeMiddle()
