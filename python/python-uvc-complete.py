#!/usr/bin/env python3
import fcntl
import mmap
import struct
import os
import time
import select
import errno
import sys
import array
from ctypes import (
    Structure, Union, c_char, c_uint32, c_uint8, c_int32, c_uint16, c_long,
    sizeof, addressof, pointer, cast, POINTER, create_string_buffer,
    memmove, memset, c_int
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

# V4L2 buffer types and memory types
V4L2_BUF_TYPE_VIDEO_OUTPUT = 2
V4L2_MEMORY_MMAP = 1
V4L2_FIELD_NONE = 1

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

# V4L2 formats
V4L2_PIX_FMT_YUYV = 0x56595559

# Structures
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

class v4l2_requestbuffers(Structure):
    _fields_ = [
        ('count', c_uint32),
        ('type', c_uint32),
        ('memory', c_uint32),
        ('reserved', c_uint32 * 2)
    ]

class v4l2_buffer_union(Union):
    _fields_ = [
        ('offset', c_uint32),
        ('userptr', c_long),
        ('planes', POINTER(c_uint32)),
        ('fd', c_int32)
    ]

class v4l2_buffer(Structure):
    _fields_ = [
        ('index', c_uint32),
        ('type', c_uint32),
        ('bytesused', c_uint32),
        ('flags', c_uint32),
        ('field', c_uint32),
        ('timestamp', c_long * 2),
        ('timecode', c_uint8 * 24),
        ('sequence', c_uint32),
        ('memory', c_uint32),
        ('m', v4l2_buffer_union),
        ('length', c_uint32),
        ('reserved2', c_uint32),
        ('reserved', c_uint32)
    ]

class usb_ctrlrequest(Structure):
    _fields_ = [
        ('bRequestType', c_uint8),
        ('bRequest', c_uint8),
        ('wValue', c_uint16),
        ('wIndex', c_uint16),
        ('wLength', c_uint16),
    ]

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
        self.buffers = []
        self.frame_count = 0
        self.width = 640
        self.height = 360

state = DeviceState()

def create_test_pattern(width, height, frame_count):
    """Generate a moving checkerboard pattern"""
    pattern = bytearray(width * height * 2)  # YUY2 format
    square_size = 32
    horizontal_offset = frame_count % (square_size * 2)
    
    WHITE = (0x80, 0xeb, 0x80, 0xeb)  # Y1 U Y2 V
    GRAY = (0x80, 0x7F, 0x7F, 0x7F)   # Y1 U Y2 V
    
    for y in range(height):
        for x in range(0, width, 2):  # Process 2 pixels at a time for YUY2
            shifted_x = (x + horizontal_offset) % width
            is_white = ((y // square_size) + (shifted_x // square_size)) % 2 == 0
            color = WHITE if is_white else GRAY
            idx = (y * width + x) * 2
            pattern[idx:idx + 4] = color
            
    return pattern

def setup_video_buffers(fd):
    """Set up memory mapped buffers"""
    # Request buffers
    reqbuf = v4l2_requestbuffers()
    reqbuf.count = 4
    reqbuf.type = V4L2_BUF_TYPE_VIDEO_OUTPUT
    reqbuf.memory = V4L2_MEMORY_MMAP
    
    fcntl.ioctl(fd, VIDIOC_REQBUFS, reqbuf)
    print(f"Requested {reqbuf.count} buffers")
    
    # Query and map buffers
    for i in range(reqbuf.count):
        buf = v4l2_buffer()
        buf.index = i
        buf.type = V4L2_BUF_TYPE_VIDEO_OUTPUT
        buf.memory = V4L2_MEMORY_MMAP
        
        fcntl.ioctl(fd, VIDIOC_QUERYBUF, buf)
        
        mm = mmap.mmap(fd, buf.length, 
                      flags=mmap.MAP_SHARED,
                      prot=mmap.PROT_READ | mmap.PROT_WRITE,
                      offset=buf.m.offset)
        
        state.buffers.append({
            'buffer': mm,
            'length': buf.length,
            'used': False
        })
        print(f"Mapped buffer {i}: length={buf.length}")
    
    return len(state.buffers)

def queue_buffer(fd, index, data=None):
    """Queue a buffer to the device"""
    if data:
        state.buffers[index]['buffer'].seek(0)
        state.buffers[index]['buffer'].write(data)
    
    buf = v4l2_buffer()
    buf.index = index
    buf.type = V4L2_BUF_TYPE_VIDEO_OUTPUT
    buf.memory = V4L2_MEMORY_MMAP
    buf.length = state.buffers[index]['length']
    
    state.buffers[index]['used'] = True
    fcntl.ioctl(fd, VIDIOC_QBUF, buf)

def dequeue_buffer(fd):
    """Dequeue a buffer from the device"""
    buf = v4l2_buffer()
    buf.type = V4L2_BUF_TYPE_VIDEO_OUTPUT
    buf.memory = V4L2_MEMORY_MMAP
    
    fcntl.ioctl(fd, VIDIOC_DQBUF, buf)
    state.buffers[buf.index]['used'] = False
    return buf.index

def set_video_format(fd):
    """Set the video format on the device"""
    fmt = v4l2_format()
    fmt.type = V4L2_BUF_TYPE_VIDEO_OUTPUT
    fmt.u.fmt.pix.width = state.width
    fmt.u.fmt.pix.height = state.height
    fmt.u.fmt.pix.pixelformat = V4L2_PIX_FMT_YUYV
    fmt.u.fmt.pix.field = V4L2_FIELD_NONE
    fmt.u.fmt.pix.sizeimage = state.width * state.height * 2
    fmt.u.fmt.pix.bytesperline = state.width * 2
    
    try:
        fcntl.ioctl(fd, VIDIOC_S_FMT, fmt)
        print("Video format set successfully")
        state.format_set = True
        return 0
    except Exception as e:
        print(f"Failed to set video format: {e}")
        return -1

def start_streaming(fd):
    """Start the video streaming"""
    if not state.format_set:
        if set_video_format(fd) < 0:
            return -1
    
    # Initialize buffers if not already done
    if not state.buffers:
        if setup_video_buffers(fd) <= 0:
            return -1
    
    # Queue initial buffers with test pattern
    for i in range(len(state.buffers)):
        pattern = create_test_pattern(state.width, state.height, state.frame_count)
        state.frame_count += 1
        queue_buffer(fd, i, pattern)
    
    # Start streaming
    buf_type = c_int(V4L2_BUF_TYPE_VIDEO_OUTPUT)
    fcntl.ioctl(fd, VIDIOC_STREAMON, buf_type)
    print("Streaming started")
    return 0

def stop_streaming(fd):
    """Stop the video streaming"""
    buf_type = c_int(V4L2_BUF_TYPE_VIDEO_OUTPUT)
    try:
        fcntl.ioctl(fd, VIDIOC_STREAMOFF, buf_type)
        print("Streaming stopped")
    except Exception as e:
        print(f"Error stopping stream: {e}")
    
    # Clear buffer state
    for buf in state.buffers:
        buf['used'] = False
    state.streaming = False

def init_streaming_control(ctrl):
    """Initialize streaming control with default values"""
    ctrl.bmHint = 1
    ctrl.bFormatIndex = 1
    ctrl.bFrameIndex = 1
    ctrl.dwFrameInterval = 333333  # 30 fps
    ctrl.wKeyFrameRate = 0
    ctrl.wPFrameRate = 0
    ctrl.wCompQuality = 0
    ctrl.wCompWindowSize = 0
    ctrl.wDelay = 0
    ctrl.dwMaxVideoFrameSize = state.width * state.height * 2  # YUY2
    ctrl.dwMaxPayloadTransferSize = 3072
    ctrl.dwClockFrequency = 48000000
    ctrl.bmFramingInfo = 3
    ctrl.bPreferedVersion = 1
    ctrl.bMinVersion = 1
    ctrl.bMaxVersion = 1

def handle_request(ctrl, req, response):
    """Handle a specific UVC request"""
    if req.bRequest == UVC_GET_CUR:
        print("-> GET_CUR request")
        memmove(addressof(response.data), addressof(ctrl), sizeof(uvc_streaming_control))
        response.length = sizeof(uvc_streaming_control)
    elif req.bRequest == UVC_GET_MIN:
        print("-> GET_MIN request")
        temp_ctrl = uvc_streaming_control()
        init_streaming_control(temp_ctrl)
        memmove(addressof(response.data), addressof(temp_ctrl), sizeof(uvc_streaming_control))
        response.length = sizeof(uvc_streaming_control)
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
        response.data[0] = 0x03
        response.length = 1
    elif req.bRequest == UVC_GET_LEN:
        print("-> GET_LEN request")
        response.data[0] = sizeof(uvc_streaming_control)
        response.data[1] = 0x00
        response.length = 2

def handle_connect_event(fd, event):
    print("UVC_EVENT_CONNECT")
    init_streaming_control(state.probe_control)
    init_streaming_control(state.commit_control)
    state.connected = True
    return None

def handle_disconnect_event(fd, event):
    print("UVC_EVENT_DISCONNECT")
    if state.streaming:
        stop_streaming(fd)
    state.connected = False
    return None

def handle_streamon_event(fd, event):
    print("UVC_EVENT_STREAMON")
    if start_streaming(fd) == 0:
        state.streaming = True
    return None

def handle_streamoff_event(fd, event):
    print("UVC_EVENT_STREAMOFF")
    stop_streaming(fd)
    return None

def handle_setup_event(fd, event):
    print("\nUVC_EVENT_SETUP")
    req = event.u.req
    response = uvc_request_data()
    response.length = -errno.EL2HLT

    print(f"Setup Request:")
    print(f"  bmRequestType: 0x{req.bRequestType:02x}")
    print(f"  bRequest: 0x{req.bRequest:02x}")
    print(f"  wValue: 0x{req.wValue:04x}")
    print(f"  wIndex: 0x{req.wIndex:04x}")
    print(f"  wLength: {req.wLength}")

    if req.bRequestType & USB_TYPE_MASK == USB_TYPE_STANDARD:
        print("  USB standard request")
    elif req.bRequestType & USB_TYPE_MASK == USB_TYPE_CLASS:
        print("  USB class request")

    cs = (req.wValue >> 8) & 0xFF
    print(f"  Control Selector: 0x{cs:02x}")

    if cs == UVC_VS_PROBE_CONTROL or cs == UVC_VS_COMMIT_CONTROL:
        ctrl = state.probe_control if cs == UVC_VS_PROBE_CONTROL else state.commit_control
        
        if req.bRequestType == 0xA1:  # GET
            handle_request(ctrl, req, response)
        elif req.bRequestType == 0x21:  # SET
            if req.bRequest == UVC_SET_CUR:
                print(f"-> SET_CUR request for {'PROBE' if cs == UVC_VS_PROBE_CONTROL else 'COMMIT'}")
                state.current_control = cs
                response.length = req.wLength

    return response

def handle_data_event(fd, event):
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
        # After commit, prepare for streaming
        if not state.format_set:
            set_video_format(fd)
    
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