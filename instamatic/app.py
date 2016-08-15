#!/usr/bin/env python

import sys, os
import numpy as np

from pyscope import jeolcom, simtem
from camera import gatanOrius, save_image_and_header
from find_crystals import find_objects, plot_props
from TEMController import TEMController

from IPython import embed

from calibration import CalibResult, load_img
import matplotlib.pyplot as plt
from find_crystals import find_holes

import pickle

CALIB100X = "calib.pickle"
CALIBBEAMSHIFT = "calibbeamshift.pickle"
HOLE_COORDS = "hole_coords.npy"
EXPERIMENT = "experiment.pickle"

def initialize():
    try:
        tem = jeolcom.Jeol()
        cam = gatanOrius()
    except WindowsError:
        print " >> Could not connect to JEOL, using SimTEM instead..."
        tem = simtem.SimTEM()
        cam = gatanOrius(simulate=True)
    ctrl = TEMController(tem, cam)
    return ctrl

def load_calib():
    if os.path.exists(CALIB100X):
        d = pickle.load(open(CALIB100X, "r"))
        calib = CalibResult(**d)
    else:
        raise IOError("\n >> Please run instamatic.calibrate100x first.")
    return calib

def load_hole_stage_positions():
    if os.path.exists(HOLE_COORDS):
        coords = np.load(HOLE_COORDS)
    else:
        raise IOError("\n >> Please run instamatic.map_holes_on_grid first.")
    return coords

def load_calib_beamshift():
    if os.path.exists(CALIBBEAMSHIFT):
        d = pickle.load(open(CALIBBEAMSHIFT, "r"))
        calib = CalibResult(**d)
    else:
        raise IOError("\n >> Please run instamatic.calibrate_beamshift first.")
    return calib

def load_experiment():
    print os.path.abspath(".")
    if os.path.exists(EXPERIMENT):
        d = pickle.load(open(EXPERIMENT, "r"))
    else:
        raise IOError("\n >> Please run instamatic.prepare_experiment first.")
    return d


def circle_center(A, B, C):
    """Finds the center of a circle from 3 positions on the circumference

    Adapted from http://stackoverflow.com/a/21597515"""
    Ax, Ay = A
    Bx, By = B
    Cx, Cy = C
    
    yDelta_a = By - Ay
    xDelta_a = Bx - Ax
    yDelta_b = Cy - By
    xDelta_b = Cx - Bx
    
    aSlope = yDelta_a/xDelta_a
    bSlope = yDelta_b/xDelta_b
    
    center_x = (aSlope*bSlope*(Ay - Cy) + bSlope*(Ax + Bx)
        - aSlope*(Bx+Cx) )/(2* (bSlope-aSlope) )
    center_y = -1*(center_x - (Ax+Bx)/2)/aSlope +  (Ay+By)/2
    
    return np.array([center_x, center_y])


def chunks(l, n):
    """Yield successive n-sized chunks from l."""
    for i in range(0, len(l), n):
        yield l[i:i+n]


def get_grid(n, r, borderwidth=0.8):
    """Make a grid (size=n*n), and return the coordinates of those
    fitting inside a circle (radius=r)
    n: `int`
        Used to define a mesh n*n
    r: `float`
        radius of hole
    borderwidth: `float`, 0.0 - 1.0
        define a border around the circumference not to place any points
        should probably be related to the effective camera size: 
    """
    yr = xr = np.linspace(-1, 1, n)
    xgrid, ygrid = np.meshgrid(xr, yr)
    sel = xgrid**2 + ygrid**2 < 1.0*borderwidth
    xvals = xgrid[sel].flatten()
    yvals = ygrid[sel].flatten()
    return xvals*r, yvals*r 


def seek_and_destroy(img, calib, ctrl=None, plot=False):
    """Routine that handles seeking crystals, and shooting them with the beam"""

    exposure = 1.0
    binsize = 1

    crystals = find_crystals(img)
    if plot:
        plot_props(crystals)

    center_beamshift = ctrl.beamshift.x, ctrl.beamshift.y

    for crystal in crystals:
        x, y = crystal.centroid

        x_shift, y_shift = calib.pixelcoords_to_beamshift(x, y)

        ctrl.activate_nanobeam()
        ctrl.beamshift.goto(x=x_shift, y=y_shift)
        ctrl.activate_diffraction_mode()

        arr, h = ctrl.getImage(binsize=binsize, exposure=exposure, comment="Diffraction data")


def seek_and_destroy_entry():
    exposure = 0.2
    binsize = 1

    calib = load_calib_beamshift()

    fns = sys.argv[1:]
    if fns:
        for fn in fns:
            arr, header = load_img(fn)
            seek_and_destroy(arr, calib, plot=True)
    else:
        ctrl = initialize()
        arr = ctrl.getImage(binsize=binsize, exposure=exposure, comment="Seek and destroy")
    
        seek_and_destroy(arr, calib, plot=True)
    
        # save_image(outfile, arr)
        # save_header(outfile, h)


def find_hole_center_high_mag_from_files(fns):
    centers = []
    vects = []
    print "Now processing:", fns
    for i,fn in enumerate(fns):
        img, header = load_img(fn)
        img = img.astype(int)
        x,y = np.array([header["StagePosition"]["x"], header["StagePosition"]["y"]])
        if i != 3:
            vects.append((x,y))

    center = circle_center(*vects)
    r = np.mean([np.linalg.norm(v-center) for v in vects]) # approximate radius
    return center, r


def fake_circle():
    import random
    da = random.randrange(-5,5) * 2.2
    db = random.randrange(-5,5) * 2.2
    vects = []
    for i in range(3):
        a = random.randrange(-100,100)/100.0
        b = (1 - a**2)**0.5
        vects.append((a+da, b+db))
    return vects


def find_hole_center_high_mag_interactive(ctrl=None):
    if not ctrl:
        ctrl = initialize()
    while True:
        print "\nPick 3 points centering the camera on the edge of a hole"
        print " 1 >> ",
        raw_input()
        v1 = ctrl.stageposition.x, ctrl.stageposition.y
        print v1
        print " 2 >> ",
        raw_input()
        v2 = ctrl.stageposition.x, ctrl.stageposition.y
        print v2
        print " 3 >> ",
        raw_input()
        v3 = ctrl.stageposition.x, ctrl.stageposition.y
        print v3
    
        # in case of simulation mode generate a fake circle
        if v1 == (0, 0) and v2 == (0, 0) and v3 == (0, 0):
            v1, v2, v3 = fake_circle()
        
        try:
            center = circle_center(v1, v2, v3)
            radius = np.mean([np.linalg.norm(np.array(v)-center) for v in (v1, v2, v3)])
        except:
            print "Could not determine circle center/radius... Try again"
            continue
        print "Center:", center
        print "Radius:", radius
        
        answer = raw_input("\ncontinue? \n [YES/no/redo] >> ")
        
        if "n" in answer:
            yield center, radius
            raise StopIteration
        elif "r" in answer:
            continue
        else:
            yield center, radius

def update_experiment_with_hole_coords(coords):
    experiment = load_experiment()

    radius = experiment["radius"]

    shifts = []
    print "\n >> Trying to find shift correction factor lowmag -> mag1 coords..."
    for xy in experiment["centers"]:
        dist_sq = np.sum((coords - xy)**2, axis=1)
        nearest = np.argmin(dist_sq)
        val = dist_sq[nearest]
    
        if val**0.5 < radius:
            shift = coords[nearest] - xy
            shifts.append(shift)
            print "Shift:", shift

    mean_shift = np.mean(np.array(shifts), axis=0)
    print " >> Correction factor (mean shift): {}".format(mean_shift)

    corrected = coords - mean_shift

    plot = False
    if plot:
        plt.scatter(*coords.T, color="grey", label="original lowmag coords")
        plt.scatter(*corrected.T, color="blue", label="corrected lowmag coords")
        plt.scatter(*experiment["centers"].T, color="red", label="picked mag1 coords")
        plt.legend()
        plt.show()

    experiment["centers_mag1"] = experiment["centers"]
    experiment["stagepos_shift"] = mean_shift 
    experiment["centers"] = corrected

    pickle.dump(experiment, open(EXPERIMENT, "w"))
    print " >> Wrote {} coordinates to file {}".format(len(coords), EXPERIMENT)


def update_experiment_with_hole_coords_entry():
    if len(sys.argv) == 1:
        coords = load_hole_stage_positions()
    else:
        fn = sys.argv[1]
        coords = np.load(fn)

    update_experiment_with_hole_coords(coords)


def prepare_experiment(centers, radii):
    centers = np.array(centers)

    r_mean = np.mean(radii)
    r_std = np.std(radii)
    print "Average radius: {}+-{} ({:.1%})".format(r_mean, r_std, (r_std/r_mean))
    
    x_offsets, y_offsets = get_grid(n=7, r=r_mean)

    pickle.dump({
        "centers": centers,
        "radius": r_mean,
        "x_offsets": x_offsets,
        "y_offsets": y_offsets
        }, open("experiment.pickle","w"))


def prepare_experiment_entry():
    # fns = sys.argv[1:]
    centers = []
    radii = []
    fns = sys.argv[1:]

    if fns:
        for fns in chunks(sys.argv[1:], 3):
            center, radius = find_hole_center_high_mag_from_files(fns)
            centers.append(center)
            radii.append(radius)
    else:
        for center, radius in find_hole_center_high_mag_interactive():
            centers.append(center)
            radii.append(radius)

    prepare_experiment(centers, radii)

    try:
        plot_experiment_entry()
    except IOError:
        pass

def plot_experiment(ctrl=None):
    d = load_experiment()
    calib = load_calib()
    centers = d["centers"]
    radius = d["radius"]
    x_offsets = d["x_offsets"]
    y_offsets = d["y_offsets"]
    
    fig = plt.figure(figsize=(10, 10))
    ax = fig.add_subplot(111)

    plt.scatter(*calib.reference_position)

    for i, (x_cent, y_cent) in enumerate(centers):
        plt.scatter(x_cent, y_cent)
        plt.scatter(x_offsets+x_cent, y_offsets+y_cent, s=1, picker=8, label=str(i))
        circle = plt.Circle((x_cent, y_cent), radius, edgecolor='r', facecolor="none", alpha=0.5)
        ax.add_artist(circle)

    skiplist = []    
    def onclick(event):
        click = event.mouseevent.button
        ind = event.ind[0]
        label = int(event.artist.get_label())

        if click == 1:
            x_cent, y_cent = centers[label]
            x_offset = x_offsets[ind]
            y_offset = y_offsets[ind]
    
            x = x_cent+x_offset
            y = y_cent+y_offset
    
            print "Pick event -> {} -> ind: {}, xdata: {:.3e}, ydata: {:.3e}".format(label, ind, x, y)
            ctrl.stageposition.goto(x=x, y=y)
            print ctrl.stageposition
            print
        elif click == 3:
            alpha = event.artist.get_alpha()
            if (not alpha) or alpha == 1.0:
                skiplist.append(int(label))
                event.artist.set_alpha(0.2)
            else:
                skiplist.remove(int(label))
                event.artist.set_alpha(None)

            fig.canvas.draw()
            # print skiplist

    fig.canvas.mpl_connect('pick_event', onclick)
    # fig.canvas.mpl_connect('button_press_event', onpress)


    plt.axis('equal')
    
    minval = centers.min()
    maxval = centers.max()
    plt.xlim(minval - abs(minval*0.2), maxval + abs(maxval*0.2))
    plt.ylim(minval - abs(minval*0.2), maxval + abs(maxval*0.2))

    plt.show()

def plot_experiment_entry():
    ctrl = initialize()
    plot_experiment(ctrl=ctrl)

def do_experiment(ctrl=None):
    d = load_experiment()
    centers = d["centers"]
    radius = d["radius"]
    x_offsets = d["x_offsets"]
    y_offsets = d["y_offsets"]

    binsize = 1
    exposure = 0.2
    plot = False

    print "binsize = {} | exposure = {}".format(binsize, exposure)
    print
    print "Usage:"
    print "    type 'next' to go to the next hole"
    print "    type 'exit' to interrupt the script"
    print "    type 'auto' to enable automatic mode (until next hole)"
    print "    type 'plot' to toggle plotting mode"

    i = 0
    for x, y in centers:
        try:
            ctrl.stageposition.goto(x=x, y=y)
        except ValueError as e:
            print e
            print " >> Moving to next hole..."
            print
            i += 1
            continue

        print "\n >> Going to next hole center \n    ->", ctrl.stageposition

        j = 0
        auto = False
        for x_offset, y_offset in zip(x_offsets, y_offsets):
            try:
                ctrl.stageposition.goto(x=x+x_offset, y=y+y_offset)
            except ValueError as e:
                print e
                print " >> Moving to next position..."
                print
                j += 1
                continue

            outfile = "image_{:04d}_{:04d}".format(i,j)

            if not auto:
                answer = raw_input("\n (Press <enter> to save an image and continue) \n >> ")
                if answer == "exit":
                    print " >> Interrupted..."
                    exit()
                elif answer == "next":
                    print " >> Going to next hole"
                    break
                elif answer == "auto":
                    auto = True
                elif answer == "plot":
                    plot = not plot

            comment = "Hole {} image {}\nx_offset={:.2e} y_offset={:.2e}".format(i, j, x_offset, y_offset)

            arr, h = ctrl.getImage(binsize=binsize, exposure=exposure, comment=comment)
    
            save_image_and_header(outfile, img=arr, header=h)

            if plot:
                plt.imshow(arr, cmap="gray")
                plt.title(comment)
                plt.show()

            j += 1

        i += 1


def do_experiment_entry():
    ctrl = initialize()
    do_experiment(ctrl)


def plot_hole_stage_positions(coords=None, calib=None, ctrl=None, picker=False):
    if calib is None:
        calib = load_calib()
    if coords is None:
        coords = load_hole_stage_positions()
    fig = plt.figure()
    reflabel = "Reference position"
    holelabel = "Hole position"
    plt.scatter(*calib.reference_position, c="red", label="Reference position", picker=8)
    plt.scatter(coords[:,0], coords[:,1], c="blue", label="Hole position", picker=8)
    for i, (x,y) in enumerate(coords):
        plt.text(x, y, str(i), size=20)

    def onclick(event):
        ind = event.ind[0]
        
        label = event.artist.get_label()
        if label == reflabel:
            xval, yval = calib.reference_position
        else:
            xval, yval = coords[ind]

        print "Pick event -> {} -> ind: {}, xdata: {:.3e}, ydata: {:.3e}".format(label, ind, xval, yval)
        ctrl.stageposition.goto(x=xval, y=yval)
        print ctrl.stageposition
        print

    if picker:
        fig.canvas.mpl_connect('pick_event', onclick)

    plt.legend()
    plt.axis('equal')
    
    minval = coords.min()
    maxval = coords.max()
    plt.xlim(minval - abs(minval)*0.2, maxval + abs(maxval)*0.2)
    plt.ylim(minval - abs(minval)*0.2, maxval + abs(maxval)*0.2)
    
    plt.show()


def goto_hole_entry():
    ctrl = initialize()

    calib = load_calib()
    coords = load_hole_stage_positions()

    try:
        num = int(sys.argv[1])
    except IndexError:
        print "\nUsage: instamatic.goto_hole [N]"
        print
        plot_hole_stage_positions(coords, calib, ctrl=ctrl, picker=True)
        # num = int(raw_input( "Which number to go to? \n >> [0-{}] ".format(len(coords))))
    else:
        if num > len(coords):
            print " >> '{}' not in coord list (max={})".format(num, len(coords))
            exit()
        stage_x, stage_y = coords[num]

        ctrl.stageposition.goto(x=stage_x, y=stage_y)
        print ctrl.stageposition


def cluster_mean(arr, threshold=0.00005):
    """Simple clustering/averaging routine based on fclusterdata"""
    from scipy.cluster.hierarchy import fclusterdata
    clust = fclusterdata(arr, threshold, criterion="distance")
    
    merged = []
    for i in np.unique(clust):
        merged.append(np.mean(arr[clust==i], axis=0))
    return np.array(merged)


def map_holes_on_grid(fns, plot=True, save_images=False):
    calib = load_calib()
    print
    print calib
    print
    stage_coords = []
    outfile = None
    for fn in fns:
        print "Now processing:", fn
        img, header = load_img(fn)
        img = img.astype(int)
        image_pos = np.array([header["StagePosition"]["x"], header["StagePosition"]["y"]])

        if save_images:
            outfile = os.path.splitext(fn)[0] + ".tif"

        holes = find_holes(img, header, plot=plot, fname=outfile)

        for hole in holes:
            stagepos = calib.pixelcoord_to_stagepos(hole.centroid, image_pos)
            stage_coords.append(stagepos)

    xy = np.array(stage_coords)

    threshold = 0.00005
    xy = cluster_mean(xy, threshold=threshold)
    xy = xy[xy[:,0].argsort(axis=0)]

    if plot:
        plot_hole_stage_positions(calib, xy)
    print "Found {} unique holes (threshold={})".format(len(xy), threshold)
    np.save(HOLE_COORDS, xy)

def map_holes_on_grid_entry():
    fns = sys.argv[1:]
    if not fns:
        print "Usage: instamatic.map_holes IMG1 [IMG2 ...]"
        exit()
    
    map_holes_on_grid(fns)

def calibrate100x(center_fn=None, other_fn=None, ctrl=None, confirm=True):
    from calibration import calibrate_lowmag, calibrate_lowmag_from_image_fn

    if not (center_fn or other_fn):
        if confirm and not raw_input("\n >> Go too 100x mag, and move the sample stage\nso that the grid center (clover) is in the\nmiddle of the image (type 'go'): """) == "go":
            return
        else:
            calib = calibrate_lowmag(ctrl, save_images=True)
    else:
        calib = calibrate_lowmag_from_image_fn(center_fn, other_fn)

    print "\nRotation/scalint matrix:\n", calib.transform
    print "Reference stagepos:", calib.reference_position

    print calib

    pickle.dump({
        "transform": calib.transform,
        "reference_position": calib.reference_position
        }, open(CALIB100X,"w"))

def calibrate100x_entry():

    if "help" in sys.argv:
        print """
Program to calibrate lowmag (100x) of microscope

Usage: 
prepare
    instamatic.calibrate100x
        To start live calibration routine on the microscope

    instamatic.calibrate100x CENTER_IMAGE (CALIBRATION_IMAGE ...)
       To perform calibration using pre-collected images
"""
        exit()
    elif len(sys.argv) == 1:
        ctrl = initialize()
        calibrate100x(ctrl=ctrl, save_images=True)
    else:
        center_fn = sys.argv[1]
        other_fn = sys.argv[2:]
        calibrate100x(center_fn, other_fn)


def calibrate_beamshift(center_fn=None, other_fn=None, ctrl=None, confirm=True):
    print "\nRotation/scalint matrix:\n", calib.transform
    print "Reference stagepos:", calib.reference_position

    print calib

    pickle.dump({
        "transform": calib.transform,
        "reference_position": calib.reference_position
        }, open(CALIBBEAMSHIFT, "w"))

def calibrate_beamshift_entry():
    from calibration import calibrate_highmag, calibrate_highmag_from_image_fn

    if "help" in sys.argv:
        print """
Program to calibrate beamshift of microscope

Usage: 
prepare
    instamatic.calibrate_beamshift
        To start live calibration routine on the microscope

    instamatic.calibrate_beamshift CENTER_IMAGE (CALIBRATION_IMAGE ...)
       To perform calibration using pre-collected images
"""
        exit()
    elif len(sys.argv) == 1:
        calib = calibrate_highmag(ctrl, save_images=True)
    else:
        center_fn = sys.argv[1]
        other_fn = sys.argv[2:]
        calib = calibrate_highmag_from_image_fn(center_fn, other_fn)



def main():
    print "High tension:", tem.getHighTension()
    print

    if True:
        for d in tem.getCapabilities():
            if 'get' in d["implemented"]:
                print "{:30s} : {}".format(d["name"], getattr(tem, "get"+d["name"])())

    if True:
        img, h = ctrl.getImage()

        # img = color.rgb2gray(img)
        img = np.invert(img)
        print img.min(), img.max()
        crystals = find_crystals(img)
        plot_props(img, crystals)

    # embed()


if __name__ == '__main__':
    main()
