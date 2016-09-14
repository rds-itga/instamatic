#!/usr/bin/env python

import sys, os
import numpy as np

from cross_correlate import cross_correlate

from camera import save_image_and_header
from TEMController import initialize

import fileio
from calibration import CalibResult, load_img, lsq_rotation_scaling_matrix


def calibrate_beamshift_live(ctrl, gridsize=5, stepsize=5e-5, exposure=0.1, binsize=1, save_images=False):
    """
    Calibrate pixel->beamshift coordinates live on the microscope

    ctrl: instance of `TEMController`
        contains tem + cam interface
    gridsize: `int`
        Number of grid points to take, gridsize=5 results in 25 points
    stepsize: `float`
        Size of steps for beamshift along x and y
    exposure: `float`
        exposure time
    binsize: `int`

    return:
        instance of Calibration class with conversion methods
    """

    img_cent, h = ctrl.getImage(exposure=exposure, comment="Beam in center of image")
    x_cent, y_cent = ctrl.beamshift.x, ctrl.beamshift.y
    
    if save_images:
        outfile = "calib_beamcenter"
        save_image_and_header(outfile, img=img_cent, header=h)

    beampos = []
    shifts = []
    
    n = (gridsize - 1) / 2 # number of points = n*(n+1)
    x_grid, y_grid = np.meshgrid(np.arange(-n, n+1) * stepsize, np.arange(-n, n+1) * stepsize)
    
    i = 0
    for dx,dy in np.stack([x_grid, y_grid]).reshape(2,-1).T:
        ctrl.beamshift.goto(x=x_cent+dx, y=y_cent+dy)
        print i
        print
        print ctrl.beamshift
        
        img, h = ctrl.getImage(exposure=exposure, comment="Calib image {}: dx={} - dy={}".format(i, dx, dy))
        shift = cross_correlate(img_cent, img, upsample_factor=10, verbose=False)
        
        xy = h["StagePosition"]["x"], h["StagePosition"]["y"]
        beampos.append(xy)
        shifts.append(shift)

        if save_images:
            outfile = "calib_beamshift_{:04d}".format(i)
            save_image_and_header(outfile, img=img,  header=h)
        
        i += 1
            
    print " >> Reset to center"
    ctrl.beamshift.goto(x=x_cent, y=y_cent)
    shifts = np.array(shifts)
    beampos = np.array(beampos) - np.array((x_cent, y_cent))
    
    r = lsq_rotation_scaling_matrix(shifts, beampos)

    c = CalibResult(transform=r, reference_position=np.array([x_cent, y_cent]))

    return c


def calibrate_beamshift_from_image_fn(center_fn, other_fn):
    """
    Calibrate pixel->beamshift coordinates from a set of images

    center_fn: `str`
        Reference image with the beam at the center of the image
    other_fn: `tuple` of `str`
        Set of images to cross correlate to the first reference image

    return:
        instance of Calibration class with conversion methods
    """
    img_cent, h_cent = load_img(center_fn)
    x_cent, y_cent = np.array((h_cent["BeamShift"]["x"], h_cent["BeamShift"]["y"]))
    print
    print "Center:", center_fn
    print "Beamshift: x={} | y={}".format(x_cent, y_cent)

    shifts = []
    beampos = []
    
    for fn in other_fn:
        img, h = load_img(fn)
        
        xy = h["BeamShift"]["x"], h["BeamShift"]["y"]
        print
        print "Image:", fn
        print "Beamshift: x={} | y={}".format(*xy)
        
        shift = cross_correlate(img_cent, img, upsample_factor=10, verbose=False)
        
        beampos.append(xy)
        shifts.append(shift)
        
    shifts = np.array(shifts)
    beampos = np.array(beampos) - np.array((x_cent, y_cent))
        
    r = lsq_rotation_scaling_matrix(shifts, beampos)
    
    c = CalibResult(transform=r, reference_position=np.array([x_cent, y_cent]))

    return c


def calibrate_beamshift(center_fn=None, other_fn=None, ctrl=None, confirm=True):
    if not (center_fn or other_fn):
        if confirm and not raw_input("\n >> Go too 2500x mag, and move the beam by beamshift\nso that is in the middle of the image (use reasonable size)\n(type 'go' to start): """) == "go":
            return
        else:
            calib = calibrate_beamshift_live(ctrl, save_images=True)
    else:
        calib = calibrate_beamshift_from_image_fn(center_fn, other_fn)

    print "\nRotation/scalint matrix:\n", calib.transform
    print "Reference stagepos:", calib.reference_position

    print calib

    fileio.write_calib_beamshift(calib)


def calibrate_beamshift_entry():
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
        ctrl = initialize()
        calibrate_beamshift(ctrl, save_images=True)
    else:
        center_fn = sys.argv[1]
        other_fn = sys.argv[2:]
        calibrate_beamshift(center_fn, other_fn)


if __name__ == '__main__':
    calibrate_beamshift_entry()