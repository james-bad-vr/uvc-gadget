#!/usr/bin/env python3
import fcntl
import struct
import os
import time
import select
import errno
import sys
import glob
from ctypes import (
    Structure, Union, c_char, c_uint32, c_uint8, c_int32, c_uint16, c_long,
    sizeof, addressof, pointer, cast, POINTER, create_string_buffer,
    memmove, memset
)

print(f"System endianness: {sys.byteorder}")

# IOCTL codes
VIDIOC_QUERYCAP = 0x80685600
VIDIOC_G_FMT = 0xc0d05604
VIDIOC_S_FMT = 0xc0cc5605
VIDIOC_REQBUFS = 0xc0145608
VIDIOC_QUERYBUF = 0xc0445609
VIDIOC_QBUF = 0xc044560f
VIDIOC_DQBUF = 0xc0445611
VIDIOC_STREAMON = 0x40045612
VIDIOC_STREAMOFF = 0x40045613
VIDIOC_SUBSCRIBE_EVENT = 0x4020565a
VIDIOC_DQEVENT = 0x80805659
UVCIOC_SEND_RESPONSE = 0x40405501

# UVC event types
V4L2_EVENT_PRIVATE_START = 0x08000000
UVC_EVENT_CONNECT    = V4L2_EVENT_PRIVATE_START + 0
UVC_EVENT_DISCONNECT = V4L2_EVENT_PRIVATE_START + 1
UVC_EVENT_STREAMON   = V4L2_EVENT_PRIVATE_START + 2
UVC_EVENT_STREAMOFF  = V4L2_EVENT_PRIVATE_START + 3
UVC_EVENT_SETUP      = V4L2_EVENT_PRIVATE_START + 4
UVC_EVENT_DATA       = V4L2_EVENT_PRIVATE_START + 5

# UVC control selectors
UVC_VS_PROBE_CONTROL = 0x01
UVC_VS_COMMIT_CONTROL = 0x02

# UVC requests
UVC_SET_CUR = 0x01
UVC_GET_CUR = 0x81
UVC_GET_MIN = 0x82
UVC_GET_MAX = 0x83
UVC_GET_RES = 0x84
UVC_GET_LEN = 0x85
UVC_GET_INFO = 0x86
UVC_GET_DEF = 0x87

# USB types
USB_TYPE_MASK = 0x60
USB_TYPE_STANDARD = 0x00
USB_TYPE_CLASS = 0x20

# V4L2 formats and flags
V4L2_PIX_FMT_YUYV = 0x56595559
V4L2_BUF_TYPE_VIDEO_OUTPUT = 2
V4L2_FIELD_NONE = 1

# Add these constants
UVC_CT_GAIN_CONTROL = 0x04
UVC_CT_GAMMA_CONTROL = 0x09
UVC_CT_BRIGHTNESS_CONTROL = 0x02

class v4l2_capability(Structure):
    _fields_ = [
        ("driver", c_char * 16),
        ("card", c_char * 32),
        ("bus_info", c_char * 32),
        ("version", c_uint32),
        ("capabilities", c_uint32),
        ("device_caps", c_uint32),
        ("reserved", c_uint32 * 3)
    ]

class usb_ctrlrequest(Structure):
    _pack_ = 1
    _fields_ = [
        ('bRequestType', c_uint8),
        ('bRequest', c_uint8),
        ('wValue', c_uint16),
        ('wIndex', c_uint16), 
        ('wLength', c_uint16)
    ]

    def __str__(self):
        return (f"bRequestType: 0x{self.bRequestType:02x}\n"
                f"bRequest: 0x{self.bRequest:02x}\n"
                f"wValue: 0x{self.wValue:04x}\n"
                f"wIndex: 0x{self.wIndex:04x}\n"
                f"wLength: {self.wLength}")

class uvc_request_data(Structure):
    _fields_ = [
        ('length', c_int32),
        ('data', c_uint8 * 60),
    ]

class uvc_streaming_control(Structure):
    _pack_ = 1
    _fields_ = [
        ('bmHint', c_uint16),
        ('bFormatIndex', c_uint8),
        ('bFrameIndex', c_uint8),
        ('dwFrameInterval', c_uint32),
        ('wKeyFrameRate', c_uint16),
        ('wPFrameRate', c_uint16),
        ('wCompQuality', c_uint16),
        ('wCompWindowSize', c_uint16),
        ('wDelay', c_uint16),
        ('dwMaxVideoFrameSize', c_uint32),
        ('dwMaxPayloadTransferSize', c_uint32),
        ('dwClockFrequency', c_uint32),
        ('bmFramingInfo', c_uint8),
        ('bPreferedVersion', c_uint8),
        ('bMinVersion', c_uint8),
        ('bMaxVersion', c_uint8),
    ]

class uvc_event(Union):
    _fields_ = [
        ('req', usb_ctrlrequest),
        ('data', uvc_request_data),
    ]

class timeval(Structure):
    _fields_ = [
        ('tv_sec', c_long),
        ('tv_usec', c_long)
    ]

class v4l2_event(Structure):
    _fields_ = [
        ('type', c_uint32),
        ('u', uvc_event),
        ('pending', c_uint32),
        ('sequence', c_uint32),
        ('timestamp', timeval),
        ('id', c_uint32),
        ('reserved', c_uint32 * 8)
    ]

class v4l2_event_subscription(Structure):
    _fields_ = [
        ('type', c_uint32),
        ('id', c_uint32),
        ('flags', c_uint32),
        ('reserved', c_uint32 * 5)
    ]

class v4l2_pix_format(Structure):
    _fields_ = [
        ('width', c_uint32),
        ('height', c_uint32),
        ('pixelformat', c_uint32),
        ('field', c_uint32),
        ('bytesperline', c_uint32),
        ('sizeimage', c_uint32),
        ('colorspace', c_uint32),
        ('priv', c_uint32),
        ('flags', c_uint32),
        ('ycbcr_enc', c_uint32),
        ('quantization', c_uint32),
        ('xfer_func', c_uint32),
    ]

class v4l2_format(Structure):
    class _u(Union):
        class _fmt(Structure):
            _fields_ = [('pix', v4l2_pix_format)]
        _fields_ = [('fmt', _fmt)]
    _fields_ = [
        ('type', c_uint32),
        ('u', _u)
    ]

# Global state
class DeviceState:
    def __init__(self):
        self.probe_control = uvc_streaming_control()
        self.commit_control = uvc_streaming_control()
        self.current_control = None
        self.streaming = False
        self.connected = False
        self.format_set = False

state = DeviceState()

class UVCConfig:
    def __init__(self):
        self.control_interface = 0
        self.streaming_interface = 1
        self.streaming_interval = 1
        self.streaming_maxburst = 0
        self.streaming_maxpacket = 2048
        self.formats = []

class VideoFormat:
    def __init__(self):
        self.index = 0
        self.guid = None
        self.frames = []

class VideoFrame:
    def __init__(self):
        self.index = 0
        self.width = 0
        self.height = 0
        self.intervals = []

def find_configfs_mount():
    """Find the ConfigFS mount point by reading /proc/mounts"""
    print("configfs_mount_point: Searching for ConfigFS mount point.")
    with open('/proc/mounts', 'r') as f:
        for line in f:
            fields = line.split()
            if fields[2] == 'configfs':
                print(f"configfs_mount_point: Found ConfigFS entry in '/proc/mounts': '{line}'")
                return fields[1]
    return None

def read_attribute(path, attr_name, binary=False):
    """Read an attribute from a ConfigFS file"""
    full_path = os.path.join(path, attr_name)
    try:
        mode = 'rb' if binary else 'r'
        with open(full_path, mode) as f:
            content = f.read()
            if not binary:
                content = content.strip()
            print(f"attribute_read: Successfully read {len(content)} bytes from file '{full_path}'")
            return content
    except Exception as e:
        print(f"Failed to read attribute {attr_name} from {path}: {e}")
        return None

def format_guid(guid_bytes):
    """Format binary GUID data as string"""
    if not guid_bytes or len(guid_bytes) != 16:
        return None
    # Convert binary GUID to string representation
    guid_parts = [
        guid_bytes[0:4][::-1].hex(),
        guid_bytes[4:6][::-1].hex(),
        guid_bytes[6:8][::-1].hex(),
        guid_bytes[8:10].hex(),
        guid_bytes[10:16].hex()
    ]
    return f"{{{'-'.join(guid_parts)}}}"

def parse_uvc_function():
    """Parse UVC function configuration from ConfigFS"""
    print("configfs_parse_uvc_function")
    
    # Find ConfigFS mount point
    configfs_mount = find_configfs_mount()
    if not configfs_mount:
        return None

    # Find UVC function directory
    uvc_func_pattern = os.path.join(configfs_mount, "usb_gadget/*/functions/uvc.*")
    uvc_funcs = glob.glob(uvc_func_pattern)
    if not uvc_funcs:
        return None
    
    uvc_func_path = uvc_funcs[0]
    print(f"configfs_find_uvc_function: Found function path='{uvc_func_path}'")

    config = UVCConfig()

    # Read streaming parameters
    config.streaming_interval = int(read_attribute(uvc_func_path, "streaming_interval") or "1")
    config.streaming_maxburst = int(read_attribute(uvc_func_path, "streaming_maxburst") or "0")
    config.streaming_maxpacket = int(read_attribute(uvc_func_path, "streaming_maxpacket") or "2048")

    # Read interface numbers
    config.control_interface = int(read_attribute(os.path.join(uvc_func_path, "control"), "bInterfaceNumber") or "0")
    config.streaming_interface = int(read_attribute(os.path.join(uvc_func_path, "streaming"), "bInterfaceNumber") or "1")

    # Parse streaming formats
    streaming_class_path = os.path.join(uvc_func_path, "streaming/class/hs/h/u")
    
    # Create format object first
    video_format = VideoFormat()
    video_format.index = int(read_attribute(streaming_class_path, "bFormatIndex") or "1")
    
    # Read GUID
    guid_bytes = read_attribute(streaming_class_path, "guidFormat", binary=True)
    if guid_bytes:
        video_format.guid = format_guid(guid_bytes)

    # Find frame descriptors - only match directories with format "NNNxNNN"
    frame_pattern = os.path.join(streaming_class_path, "*x*")
    frame_dirs = [d for d in glob.glob(frame_pattern) 
                 if os.path.isdir(d) and 'x' in os.path.basename(d) 
                 and all(c.isdigit() for c in os.path.basename(d).replace('x', ''))]
    
    for frame_dir in frame_dirs:
        frame = VideoFrame()
        frame.index = int(read_attribute(frame_dir, "bFrameIndex") or "0")
        frame.width = int(read_attribute(frame_dir, "wWidth") or "0")
        frame.height = int(read_attribute(frame_dir, "wHeight") or "0")

        # Parse frame intervals
        intervals_str = read_attribute(frame_dir, "dwFrameInterval")
        if intervals_str:
            frame.intervals = [int(i) for i in intervals_str.split()]

        if frame.width > 0 and frame.height > 0:  # Only add valid frames
            video_format.frames.append(frame)
            print(f"Added frame: {frame.width}x{frame.height} with {len(frame.intervals)} intervals")

    config.formats.append(video_format)
    return config

def init_uvc_device():
    """Initialize UVC device configuration"""
    config = parse_uvc_function()
    if not config:
        print("Failed to parse UVC configuration")
        return False

    print("\nUVC Device Configuration:")
    print(f"Control Interface: {config.control_interface}")
    print(f"Streaming Interface: {config.streaming_interface}")
    print(f"Streaming Interval: {config.streaming_interval}")
    print(f"Streaming MaxBurst: {config.streaming_maxburst}")
    print(f"Streaming MaxPacket: {config.streaming_maxpacket}")
    
    for fmt in config.formats:
        print(f"\nFormat {fmt.index}:")
        print(f"  GUID: {fmt.guid}")
        for frame in fmt.frames:
            print(f"  Frame {frame.index}: {frame.width}x{frame.height}")
            print(f"    Intervals: {frame.intervals}")

    return config

def main():
    """Main program loop"""
    fd = None
    try:
        # Initialize UVC configuration
        config = init_uvc_device()
        if not config:
            print("Failed to initialize UVC device")
            return

        device_path = "/dev/video0"
        print(f"Opening {device_path}")
        fd = os.open(device_path, os.O_RDWR | os.O_NONBLOCK)
        
        # Get device capabilities
        caps = v4l2_capability()
        fcntl.ioctl(fd, VIDIOC_QUERYCAP, caps)
        print(f"Capabilities: 0x{caps.capabilities:08x}")

        # Set video format
        if not set_video_format(fd):
            print("Failed to set video format")
            return
        
        # Subscribe to all events
        if subscribe_events(fd) < 0:
            print("Failed to subscribe to events")
            return

        print("Device ready - waiting for events...")
        epoll = select.epoll()
        epoll.register(fd, select.EPOLLPRI)

        while True:
            events = epoll.poll(1)  # 1-second timeout
            for fd, event_mask in events:
                print(f"\nReceived event with mask: 0x{event_mask:x}")
                event = v4l2_event()
                try:
                    fcntl.ioctl(fd, VIDIOC_DQEVENT, event)
                    print(f"Event type: 0x{event.type:08x}")
                    handler = EVENT_HANDLERS.get(event.type)
                    if handler:
                        print(f"Found handler for event type 0x{event.type:08x}")
                        response = handler(event)
                        if response:
                            print("Got response, sending...")
                            fcntl.ioctl(fd, UVCIOC_SEND_RESPONSE, response)
                        else:
                            print("Handler returned no response")
                    else:
                        print(f"Unhandled event type: 0x{event.type:08x}")
                except Exception as e:
                    print(f"Error handling event: {e}")
            
            time.sleep(0.01)  # Prevent busy-waiting

    except Exception as e:
        print(f"Error: {e}")
    finally:
        if fd is not None:
            print("Device closed")
            os.close(fd)

def init_streaming_control(ctrl):
    """Initialize streaming control with values from config"""
    ctrl.bmHint = 1
    ctrl.bFormatIndex = 1  # First format
    ctrl.bFrameIndex = 1   # First frame
    ctrl.dwFrameInterval = 166666  # 60fps (1/60 * 10^7)
    
    # Get these from the config we read
    frame = next((f for fmt in config.formats for f in fmt.frames if f.index == ctrl.bFrameIndex), None)
    if frame:
        ctrl.wWidth = frame.width
        ctrl.wHeight = frame.height
        ctrl.dwMaxVideoFrameSize = frame.width * frame.height * 2  # Assuming YUYV
        ctrl.dwMaxPayloadTransferSize = config.streaming_maxpacket

def handle_request(fd, ctrl, req, response):
    """Handle a UVC request"""
    print(f"Handling bRequest: 0x{req.bRequest:02x}")
    
    if req.bRequest == UVC_GET_CUR:
        print("-> GET_CUR request")
        if hasattr(ctrl, 'dwFrameInterval'):  # If it's a streaming control
            memmove(addressof(response.data), addressof(ctrl), sizeof(uvc_streaming_control))
            response.length = sizeof(uvc_streaming_control)
        else:  # Camera terminal control
            response.data[0] = 0x00
            response.length = req.wLength
    elif req.bRequest == UVC_GET_MIN:
        print("-> GET_MIN request")
        if hasattr(ctrl, 'dwFrameInterval'):
            temp_ctrl = uvc_streaming_control()
            init_streaming_control(temp_ctrl)
            memmove(addressof(response.data), addressof(temp_ctrl), sizeof(uvc_streaming_control))
            response.length = sizeof(uvc_streaming_control)
        else:
            response.data[0] = 0x00
            response.length = req.wLength
    elif req.bRequest == UVC_GET_MAX:
        print("-> GET_MAX request")
        temp_ctrl = uvc_streaming_control()
        init_streaming_control(temp_ctrl)
        memmove(addressof(response.data), addressof(temp_ctrl), sizeof(uvc_streaming_control))
        response.length = sizeof(uvc_streaming_control)
    elif req.bRequest == UVC_GET_DEF:
        print("-> GET_DEF request")
        temp_ctrl = uvc_streaming_control()
        init_streaming_control(temp_ctrl)
        memmove(addressof(response.data), addressof(temp_ctrl), sizeof(uvc_streaming_control))
        response.length = sizeof(uvc_streaming_control)
    elif req.bRequest == UVC_GET_INFO:
        print("-> GET_INFO request")
        response.data[0] = 0x03  # Supports GET/SET
        response.length = 1
    elif req.bRequest == UVC_GET_LEN:
        print("-> GET_LEN request")
        response.data[0] = sizeof(uvc_streaming_control)
        response.data[1] = 0x00
        response.length = 2
    elif req.bRequest == UVC_GET_RES:
        print("-> GET_RES request")
        response.data[0] = 0x00
        response.length = sizeof(uvc_streaming_control)
    else:
        print(f"Unhandled bRequest: 0x{req.bRequest:02x}")
        response.length = -errno.EINVAL

    return response

def handle_connect_event(event):
    print("UVC_EVENT_CONNECT")
    init_streaming_control(state.probe_control)
    init_streaming_control(state.commit_control)
    state.connected = True
    return None

def handle_disconnect_event(event):
    print("UVC_EVENT_DISCONNECT")
    state.connected = False
    return None

def handle_streamon_event(event):
    print("UVC_EVENT_STREAMON")
    state.streaming = True
    return None

def handle_streamoff_event(event):
    print("UVC_EVENT_STREAMOFF")
    state.streaming = False
    return None

def handle_setup_event(event):
    print("\nUVC_EVENT_SETUP")
    print("Raw event data (first 8 bytes):")
    raw_data = bytes(event.u.data.data[:8])
    print(' '.join(f'{b:02x}' for b in raw_data))
    
    req = usb_ctrlrequest.from_buffer_copy(raw_data)
    response = uvc_request_data()
    response.length = -errno.EL2HLT

    print(f"Setup Request:")
    print(f"  bmRequestType: 0x{req.bRequestType:02x}")
    print(f"  bRequest: 0x{req.bRequest:02x}")
    print(f"  wValue: 0x{req.wValue:04x}")
    print(f"  wIndex: 0x{req.wIndex:04x}")
    print(f"  wLength: {req.wLength}")

    cs = (req.wValue >> 8) & 0xFF
    entity_id = req.wIndex & 0xFF
    print(f"  Control Selector: 0x{cs:02x}")
    print(f"  Entity ID: 0x{entity_id:02x}")

    # Handle both streaming and camera terminal controls
    if (cs in [UVC_VS_PROBE_CONTROL, UVC_VS_COMMIT_CONTROL] or 
        cs in [UVC_CT_GAIN_CONTROL, UVC_CT_GAMMA_CONTROL, UVC_CT_BRIGHTNESS_CONTROL]):
        
        print(f"Control selector matched! cs=0x{cs:02x}")
        
        if cs in [UVC_VS_PROBE_CONTROL, UVC_VS_COMMIT_CONTROL]:
            ctrl = state.probe_control if cs == UVC_VS_PROBE_CONTROL else state.commit_control
        else:
            # For camera terminal controls, create a temporary control structure
            ctrl = create_string_buffer(4)  # 4 bytes for most camera terminal controls
            
        if req.bRequestType & 0x80:  # GET
            print("  Handling GET request")
            if req.bRequest == UVC_GET_CUR:
                print("-> GET_CUR request")
                if cs in [UVC_VS_PROBE_CONTROL, UVC_VS_COMMIT_CONTROL]:
                    memmove(addressof(response.data), addressof(ctrl), sizeof(uvc_streaming_control))
                else:
                    # For camera terminal controls, return a default value
                    response.data[0] = 0x00
                response.length = req.wLength
            elif req.bRequest == UVC_GET_MIN:
                print("-> GET_MIN request")
                response.data[0] = 0x00
                response.length = req.wLength
            elif req.bRequest == UVC_GET_MAX:
                print("-> GET_MAX request")
                response.data[0] = 0xFF
                response.length = req.wLength
            elif req.bRequest == UVC_GET_RES:
                print("-> GET_RES request")
                response.data[0] = 0x01
                response.length = req.wLength
            elif req.bRequest == UVC_GET_INFO:
                print("-> GET_INFO request")
                response.data[0] = 0x03  # Supports GET/SET
                response.length = 1
            elif req.bRequest == UVC_GET_DEF:
                print("-> GET_DEF request")
                response.data[0] = 0x80
                response.length = req.wLength
        elif req.bRequestType == 0x21:  # SET
            print("  Handling SET request")
            if req.bRequest == UVC_SET_CUR:
                print(f"  -> SET_CUR request for control 0x{cs:02x}")
                state.current_control = cs
                response.length = sizeof(uvc_streaming_control)
    else:
        print(f"Control selector 0x{cs:02x} did not match expected values")

    return response


def handle_data_event(event):
    print("\nUVC_EVENT_DATA")
    if state.current_control is None:
        return None

    data_len = min(event.u.data.length, sizeof(uvc_streaming_control))
    
    if state.current_control == UVC_VS_PROBE_CONTROL:
        print("Updating probe control")
        memmove(addressof(state.probe_control), event.u.data.data, data_len)
    elif state.current_control == UVC_VS_COMMIT_CONTROL:
        print("Updating commit control")
        memmove(addressof(state.commit_control), event.u.data.data, data_len)
    
    state.current_control = None
    return None

EVENT_HANDLERS = {
    UVC_EVENT_CONNECT: handle_connect_event,
    UVC_EVENT_DISCONNECT: handle_disconnect_event,
    UVC_EVENT_STREAMON: handle_streamon_event,
    UVC_EVENT_STREAMOFF: handle_streamoff_event,
    UVC_EVENT_SETUP: handle_setup_event,
    UVC_EVENT_DATA: handle_data_event,
}

def subscribe_events(fd):
    """Subscribe to all UVC events"""
    events = [
        UVC_EVENT_CONNECT,
        UVC_EVENT_DISCONNECT,
        UVC_EVENT_SETUP,
        UVC_EVENT_DATA,
        UVC_EVENT_STREAMON,
        UVC_EVENT_STREAMOFF
    ]
    
    for event_type in events:
        sub = v4l2_event_subscription(type=event_type)
        try:
            fcntl.ioctl(fd, VIDIOC_SUBSCRIBE_EVENT, sub)
            print(f"Subscribed to event 0x{event_type:08x}")
        except Exception as e:
            print(f"Failed to subscribe to event 0x{event_type:08x}: {e}")
            return -1
    return 0

def set_video_format(fd):
    """Set the video format on the device"""
    format = v4l2_format()
    format.type = V4L2_BUF_TYPE_VIDEO_OUTPUT
    
    try:
        fcntl.ioctl(fd, VIDIOC_G_FMT, format)
    except Exception as e:
        print(f"Failed to get format: {e}")
        return False

    # Set format parameters
    format.fmt.pix.width = 640  # Default to lowest resolution
    format.fmt.pix.height = 360
    format.fmt.pix.pixelformat = V4L2_PIX_FMT_YUYV
    format.fmt.pix.field = V4L2_FIELD_NONE
    format.fmt.pix.bytesperline = format.fmt.pix.width * 2  # YUYV uses 2 bytes per pixel
    format.fmt.pix.sizeimage = format.fmt.pix.bytesperline * format.fmt.pix.height
    format.fmt.pix.colorspace = V4L2_COLORSPACE_SRGB

    try:
        fcntl.ioctl(fd, VIDIOC_S_FMT, format)
        print("Video format set successfully")
        return True
    except Exception as e:
        print(f"Failed to set format: {e}")
        return False

if __name__ == "__main__":
    main()
