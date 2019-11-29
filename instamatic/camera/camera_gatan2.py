from pathlib import Path

import time
import numpy as np
import logging
logger = logging.getLogger(__name__)

import atexit

from instamatic import config

import sys
from instamatic.camera.gatansocket3 import GatanSocket


class CameraGatan2(object):
    """docstring for CameraGatan2"""

    def __init__(self, interface: str="gatan2"):
        """Initialize camera module """
        super().__init__()

        self.name = interface

        self.g = GatanSocket()

        self._recording = False

        self.load_defaults()

        msg = f"Camera `{self.getCameraName()}` ({self.name}) initialized"
        # print(msg)
        logger.info(msg)

        atexit.register(self.releaseConnection)

    def load_defaults(self) -> None:
        if self.name != config.cfg.camera:
            config.load(camera_name=self.name)

        self.__dict__.update(config.camera.d)

        self.streamable = False

    def getCameraType(self) -> str:
        """Get the name of the camera currently in use"""
        cfg = self.getCurrentConfig(as_dict=False)
        return cfg.CameraType

    def getDMVersion(self) -> str:
        """Get the version number of DM"""
        return self.g.GetDMVersion()

    def getDimensions(self) -> (int, int):
        """alias to getImageDimensions"""
        return self.getImageDimensions()

    def getCameraDimensions(self) -> (int, int):
        """Get the maximum dimensions reported by the camera"""
        raise NotImplementedError

    def getImageDimensions(self) -> (int, int):
        """Get the dimensions of the image"""
        bin_x, bin_y = self.getBinning()
        raise NotImplementedError

    def getPhysicalPixelsize(self) -> (int, int):
        """Returns the physical pixel size of the camera nanometers"""
        raise NotImplementedError

    def getBinning(self) -> (int, int):
        """Returns the binning corresponding to the currently selected camera config"""
        raise NotImplementedError

    def getCameraName(self) -> str:
        """Get the name reported by the camera"""
        return self.name

    def writeTiff(self, filename: str) -> None:
        """Write tiff file using the DM machinery"""
        raise NotImplementedError

    def writeTiffs(self) -> None:
        """Write a series of data in tiff format and writes them to the given `path`"""
        raise NotImplementedError

        path = Path(path)
        i = 0

        print(f"Wrote {i+1} images to {path}")

    def getImage(self, **kwargs) -> "np.array":
        """Acquire image through EMMENU and return data as np array"""
        raise NotImplementedError

    def acquireImage(self, **kwargs) -> int:
        """Acquire image through DM"""
        raise NotImplementedError

    def get_ready_for_record(self) -> None:
        self.reset_record_vars()

        while True:
            ready_for_acquire = self.get_tag("ready_for_acquire")
            if ready_for_acquire:
                break
            time.sleep(0.5)

        self.set_tag("ready_for_acquire", 0)

    def reset_record_vars(self):
        self.set_tag("start_acquire", 0)
        self.set_tag("stop_acquire", 1)
        self.set_tag("ready_for_acquire", 0)
        self.set_tag("prepare_acquire", 1)

    def start_record(self) -> None:
        cmd = 'SetPersistentNumberNote("start_acquire", 1)'
        self.g.ExecuteScript(cmd)

    def stop_record(self) -> int:
        cmd = 'SetPersistentNumberNote("stop_acquire", 1)'
        self.g.ExecuteScript(cmd)

    def stop_liveview(self) -> None:
        raise NotImplementedError

    def start_liveview(self, delay: float=3.0) -> None:
        raise NotImplementedError

    def set_exposure(self, exposure_time: int) -> None:
        """Set exposure time in ms"""
        raise NotImplementedError

    def get_exposure(self) -> int:
        """Return exposure time in ms"""
        raise NotImplementedError

    def releaseConnection(self) -> None:
        """Release the connection to the camera"""
        self.stop_liveview()

        msg = f"Connection to camera `{self.getCameraName()}` ({self.name}) released" 
        # print(msg)
        logger.info(msg)

    def set_tag(self, key: str, value: float) -> None:
        set_tag = f'SetPersistentNumberNote("{key}", {value})'
        self.g.ExecuteScript(set_tag)
        
    def get_tag(self, key: str) -> float:
        get_tag = f'number value\nGetPersistentNumberNote("{key}", value)\nExit(value)'
        return self.g.ExecuteGetDoubleScript(get_tag)

    def delete_tag(self, key: str) -> None:
        delete_tag = f'DeletePersistentNote("{key}")'
        self.g.ExecuteScript(delete_tag)


if __name__ == '__main__':
    cam = CameraGatan2()

    from IPython import embed
    embed()

    # set_tag("work_drc", work_drc)  # instamatic work drc
    # set_tag("sample_name", sample_name)  # experiment_x