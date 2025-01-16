#!/usr/bin/env python3
import fcntl
import struct
import os
import time
import select
import errno
import sys
from ctypes import (
    Structure, Union, POINTER,
    c_uint8, c_uint16, c_uint32, c_uint64,
    c_int8, c_int16, c_int32, c_int64,
    c_char, c_char_p, c_void_p, c_size_t,
    c_ulong, c_long, sizeof, addressof, memmove, byref
)
import mmap

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

# Add these constants at the top with the other constants
V4L2_MEMORY_MMAP = 1
V4L2_MEMORY_USERPTR = 2
V4L2_MEMORY_OVERLAY = 3
V4L2_MEMORY_DMABUF = 4

# Add these V4L2 buffer type constants
V4L2_BUF_TYPE_VIDEO_CAPTURE = 1
V4L2_BUF_TYPE_VIDEO_OUTPUT = 2
V4L2_BUF_TYPE_VIDEO_OVERLAY = 3
V4L2_BUF_TYPE_VBI_CAPTURE = 4
V4L2_BUF_TYPE_VBI_OUTPUT = 5
V4L2_BUF_TYPE_SLICED_VBI_CAPTURE = 6
V4L2_BUF_TYPE_SLICED_VBI_OUTPUT = 7

# V4L2 colorspace constants
V4L2_COLORSPACE_DEFAULT = 0
V4L2_COLORSPACE_SMPTE170M = 1
V4L2_COLORSPACE_SMPTE240M = 2
V4L2_COLORSPACE_REC709 = 3
V4L2_COLORSPACE_BT878 = 4
V4L2_COLORSPACE_470_SYSTEM_M = 5
V4L2_COLORSPACE_470_SYSTEM_BG = 6
V4L2_COLORSPACE_JPEG = 7
V4L2_COLORSPACE_SRGB = 8
V4L2_COLORSPACE_OPRGB = 9
V4L2_COLORSPACE_BT2020 = 10
V4L2_COLORSPACE_RAW = 11
V4L2_COLORSPACE_DCI_P3 = 12

# V4L2 xfer function constants
V4L2_XFER_FUNC_DEFAULT = 0
V4L2_XFER_FUNC_709 = 1
V4L2_XFER_FUNC_SRGB = 2

# V4L2 YCbCr encoding constants
V4L2_YCBCR_ENC_DEFAULT = 0
V4L2_YCBCR_ENC_601 = 1
V4L2_YCBCR_ENC_709 = 2
V4L2_YCBCR_ENC_XV601 = 3
V4L2_YCBCR_ENC_XV709 = 4

# V4L2 quantization constants
V4L2_QUANTIZATION_DEFAULT = 0
V4L2_QUANTIZATION_FULL_RANGE = 1
V4L2_QUANTIZATION_LIM_RANGE = 2

# Add these color constants at the top with other constants
WHITE = 0x80eb80eb
GRAY = 0x807F7F7F

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

class v4l2_timecode(Structure):
    _fields_ = [
        ('type', c_uint32),
        ('flags', c_uint32),
        ('frames', c_uint8),
        ('seconds', c_uint8),
        ('minutes', c_uint8),
        ('hours', c_uint8),
        ('userbits', c_uint8 * 4),
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

class v4l2_format_union(Union):
    _fields_ = [
        ('pix', v4l2_pix_format),
        ('raw_data', c_uint8 * 200),  # Ensure union is large enough
    ]

class v4l2_format(Structure):
    _fields_ = [
        ('type', c_uint32),
        ('fmt', v4l2_format_union),
    ]

class v4l2_requestbuffers(Structure):
    _fields_ = [
        ('count', c_uint32),
        ('type', c_uint32),
        ('memory', c_uint32),
    ]

class v4l2_plane(Structure):
    _fields_ = [
        ('bytesused', c_uint32),
        ('length', c_uint32),
        ('m', c_uint32),  # memory offset
        ('data_offset', c_uint32),
        ('reserved', c_uint32 * 11)
    ]

class v4l2_buffer_union(Union):
    _fields_ = [
        ('offset', c_uint32),
        ('userptr', c_ulong),
        ('planes', POINTER(v4l2_plane)),
        ('fd', c_int32),
    ]

class v4l2_buffer(Structure):
    _fields_ = [
        ('index', c_uint32),
        ('type', c_uint32),
        ('bytesused', c_uint32),
        ('flags', c_uint32),
        ('field', c_uint32),
        ('timestamp', timeval),
        ('timecode', v4l2_timecode),
        ('sequence', c_uint32),
        ('memory', c_uint32),
        ('m', v4l2_buffer_union),
        ('length', c_uint32),
        ('reserved2', c_uint32),
        ('reserved', c_uint32),
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

# Add these global variables at the top of the file
buffers = None
current_format = None

def main():
    """Main program loop"""
    global fd, buffers  # Make these global so event handlers can access them
    fd = None
    buffers = None
    
    try:
        device_path = "/dev/video0"
        print(f"Opening {device_path}")
        fd = os.open(device_path, os.O_RDWR | os.O_NONBLOCK)
        
        # Query device capabilities
        cap = v4l2_capability()
        fcntl.ioctl(fd, VIDIOC_QUERYCAP, cap)
        print(f"Capabilities: 0x{cap.capabilities:08x}")

        # Set video format
        if set_video_format(fd) < 0:
            print("Failed to set video format")
            return
        
        # Initialize video buffers
        buffers = init_video_buffers(fd)
        if not buffers:
            print("Failed to initialize video buffers")
            return
            
        print(f"Initialized {len(buffers)} video buffers")
        
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

    except KeyboardInterrupt:
        print("\nExiting...")
    finally:
        if buffers:
            for buf in buffers:
                buf['mmap'].close()
        if fd is not None:
            print("Device closed")
            os.close(fd)

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
    ctrl.dwMaxVideoFrameSize = 640 * 360 * 2  # YUY2
    ctrl.dwMaxPayloadTransferSize = 3072
    ctrl.dwClockFrequency = 48000000
    ctrl.bmFramingInfo = 3
    ctrl.bPreferedVersion = 1
    ctrl.bMinVersion = 1
    ctrl.bMaxVersion = 1

def set_video_format(fd):
    """Set video format to YUYV 1920x1080"""
    print("\nSetting video format")
    global current_format
    
    fmt = v4l2_format()
    fmt.type = V4L2_BUF_TYPE_VIDEO_OUTPUT
    fmt.fmt.pix.width = 1920
    fmt.fmt.pix.height = 1080
    fmt.fmt.pix.pixelformat = V4L2_PIX_FMT_YUYV
    fmt.fmt.pix.field = V4L2_FIELD_NONE
    fmt.fmt.pix.bytesperline = fmt.fmt.pix.width * 2  # 2 bytes per pixel for YUYV
    fmt.fmt.pix.sizeimage = fmt.fmt.pix.bytesperline * fmt.fmt.pix.height
    fmt.fmt.pix.colorspace = V4L2_COLORSPACE_SRGB
    fmt.fmt.pix.xfer_func = V4L2_XFER_FUNC_SRGB
    fmt.fmt.pix.ycbcr_enc = V4L2_YCBCR_ENC_601  # Standard for YUYV
    fmt.fmt.pix.quantization = V4L2_QUANTIZATION_LIM_RANGE
    
    try:
        fcntl.ioctl(fd, VIDIOC_S_FMT, fmt)
        print("Video format set successfully:")
        print(f"  Width: {fmt.fmt.pix.width}")
        print(f"  Height: {fmt.fmt.pix.height}")
        print(f"  Pixel Format: {hex(fmt.fmt.pix.pixelformat)}")
        print(f"  Bytes per line: {fmt.fmt.pix.bytesperline}")
        print(f"  Size image: {fmt.fmt.pix.sizeimage}")
        print(f"  Colorspace: {fmt.fmt.pix.colorspace}")
        current_format = fmt.fmt.pix  # Store the current format
        return True
    except Exception as e:
        print(f"Failed to set video format: {e}")
        return False

def handle_request(fd, ctrl, req, response):
    print(f"Handling bRequest: 0x{req.bRequest:02x}")
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
    elif req.bRequest == UVC_SET_CUR:
        print("-> SET_CUR request")
        # Handle specific SET_CUR logic if needed
        response.length = 0  # Acknowledge
    else:
        print(f"Unhandled bRequest: 0x{req.bRequest:02x}")

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
    """Handle stream on event"""
    print("\nUVC_EVENT_STREAMON")
    global state
    
    try:
        # Start the video stream
        buf_type = c_int32(V4L2_BUF_TYPE_VIDEO_OUTPUT)
        print("Starting video stream...")
        fcntl.ioctl(fd, VIDIOC_STREAMON, buf_type)
        print("Stream started successfully")
        
        if not current_format or not buffers:
            print("Error: Missing format or buffers")
            return None
            
        print(f"\nCurrent format:")
        print(f"  Width: {current_format.width}")
        print(f"  Height: {current_format.height}")
        print(f"  Pixel format: {hex(current_format.pixelformat)}")
        print(f"  Bytes per line: {current_format.bytesperline}")
        print(f"  Size image: {current_format.sizeimage}")
            
        # Queue initial buffers
        for buf in buffers:
            print(f"\nProcessing buffer {buf['index']}:")
            
            # Fill buffer with test pattern
            bytes_used = generate_test_pattern(buf['mmap'], current_format.width, current_format.height)
            
            v4l2_buf = v4l2_buffer()
            v4l2_buf.type = V4L2_BUF_TYPE_VIDEO_OUTPUT
            v4l2_buf.memory = V4L2_MEMORY_MMAP
            v4l2_buf.index = buf['index']
            v4l2_buf.bytesused = bytes_used
            
            try:
                fcntl.ioctl(fd, VIDIOC_QBUF, v4l2_buf)
                print(f"  Successfully queued buffer {buf['index']}")
            except Exception as e:
                print(f"  Failed to queue buffer: {e}")
                print(f"  Error details: {type(e).__name__}")
        
        # Start streaming thread
        state.streaming = True
        print("\nStarting streaming thread...")
        import threading
        thread = threading.Thread(target=streaming_thread, daemon=True)
        thread.start()
        print("Streaming thread started with ID:", thread.ident)
            
    except Exception as e:
        print(f"Failed to start stream: {e}")
        print(f"Error details: {type(e).__name__}")
    
    return None

def streaming_thread():
    """Background thread to handle continuous streaming"""
    print("\nStreaming thread started")
    frame_count = 0
    while state.streaming:
        try:
            print(f"\nFrame {frame_count}: Processing...")
            # Dequeue a buffer
            buf = v4l2_buffer()
            buf.type = V4L2_BUF_TYPE_VIDEO_OUTPUT
            buf.memory = V4L2_MEMORY_MMAP
            print(f"Trying to dequeue buffer...")
            fcntl.ioctl(fd, VIDIOC_DQBUF, buf)
            print(f"Dequeued buffer {buf.index}")
            
            # Update the test pattern
            buffer = buffers[buf.index]
            print(f"Generating test pattern for frame {frame_count}...")
            bytes_used = generate_test_pattern(
                buffer['mmap'], 
                current_format.width, 
                current_format.height,
                offset=frame_count  # Use frame_count directly for more noticeable movement
            )
            print(f"Generated pattern with {bytes_used} bytes")
            
            # Queue the buffer back
            buf.bytesused = bytes_used
            print(f"Queueing buffer {buf.index} back...")
            fcntl.ioctl(fd, VIDIOC_QBUF, buf)
            print(f"Buffer {buf.index} queued successfully")
            
            frame_count += 1
            
        except Exception as e:
            if not state.streaming:  # Expected when stopping
                print("Streaming stopped normally")
                break
            print(f"Streaming error: {e}")
            print(f"Error details: {type(e).__name__}")
            time.sleep(0.1)  # Avoid tight loop on error

def generate_test_pattern(mm, width, height, offset=0):
    """Fill buffer with a moving test pattern"""
    print(f"\nGenerating test pattern:")
    print(f"  Width: {width}")
    print(f"  Height: {height}")
    print(f"  Offset: {offset}")
    
    pattern = bytearray()
    bytes_per_line = width * 2  # 2 bytes per pixel for YUYV
    square_size = 64  # Larger squares to make pattern more visible
    horizontal_offset = offset % width  # Full width movement
    
    print(f"  Bytes per line: {bytes_per_line}")
    print(f"  Square size: {square_size}")
    print(f"  Horizontal offset: {horizontal_offset}")
    
    for y in range(height):
        for x in range(0, bytes_per_line, 4):  # Process 2 pixels (4 bytes) at a time
            pixel_x = x // 2  # Convert byte position to pixel position
            shifted_x = (pixel_x + horizontal_offset) % width
            
            # Create checkerboard pattern
            is_white = ((y // square_size) + (shifted_x // square_size)) % 2 == 0
            color = WHITE if is_white else GRAY
            
            # Write 4 bytes (2 pixels) of YUYV data
            pattern.extend(color.to_bytes(4, byteorder='little'))

    try:
        mm.seek(0)
        mm.write(bytes(pattern))  # Convert bytearray to bytes before writing
        print(f"  Successfully wrote {len(pattern)} bytes to buffer")
    except Exception as e:
        print(f"Error writing to memory map: {e}")
        print(f"Error details: {type(e).__name__}")
        raise  # Re-raise the exception to see where it's happening
        
    return len(pattern)

def handle_streamoff_event(event):
    """Handle UVC_EVENT_STREAMOFF"""
    print("UVC_EVENT_STREAMOFF")
    state.streaming = False
    
    try:
        buf_type = c_int32(V4L2_BUF_TYPE_VIDEO_OUTPUT)
        fcntl.ioctl(fd, VIDIOC_STREAMOFF, buf_type)
    except Exception as e:
        print(f"Error stopping stream: {e}")
    
    return None

def handle_setup_event(event):
    print("\nUVC_EVENT_SETUP")
    print("Raw event data (first 8 bytes):")
    # Print the first 8 bytes of raw data
    raw_data = bytes(event.u.data.data[:8])
    print(' '.join(f'{b:02x}' for b in raw_data))
    
    # Create request struct from the first 8 bytes of event data
    req = usb_ctrlrequest.from_buffer_copy(raw_data)
    response = uvc_request_data()
    response.length = -errno.EL2HLT

    print(f"Setup Request:")
    print(f"  bmRequestType: 0x{req.bRequestType:02x}")
    print(f"  bRequest: 0x{req.bRequest:02x}")
    print(f"  wValue: 0x{req.wValue:04x}")
    print(f"  wIndex: 0x{req.wIndex:04x}")
    print(f"  wLength: {req.wLength}")

    # Extract control selector from wValue
    cs = (req.wValue >> 8) & 0xFF
    print(f"  Control Selector: 0x{cs:02x}")
    print(f"Checking if cs (0x{cs:02x}) is in [{UVC_VS_PROBE_CONTROL}, {UVC_VS_COMMIT_CONTROL}]")
    
    if cs in [UVC_VS_PROBE_CONTROL, UVC_VS_COMMIT_CONTROL]:
        print(f"Control selector matched! cs=0x{cs:02x}")
        ctrl = state.probe_control if cs == UVC_VS_PROBE_CONTROL else state.commit_control
        print(f"Request type: 0x{req.bRequestType:02x}")

        if req.bRequestType & USB_TYPE_MASK == USB_TYPE_CLASS:  # Check if it's a class request
            if req.bRequestType & 0x80:  # GET
                print("  Handling GET request")
                handle_request(None, ctrl, req, response)
            else:  # SET
                print("  Handling SET request")
                if req.bRequest == UVC_SET_CUR:
                    print(f"  -> SET_CUR request for {'PROBE' if cs == UVC_VS_PROBE_CONTROL else 'COMMIT'}")
                    state.current_control = cs
                    response.length = sizeof(uvc_streaming_control)
    else:
        print(f"Control selector 0x{cs:02x} did not match expected values")
        # For debugging, let's print the expected values
        print(f"Expected values: PROBE=0x{UVC_VS_PROBE_CONTROL:02x}, COMMIT=0x{UVC_VS_COMMIT_CONTROL:02x}")

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

def init_video_buffers(fd):
    """Initialize video buffers following v4l2_alloc_buffers() in v4l2.c"""
    print("\nInitializing video buffers")
    
    # Request buffers
    req = v4l2_requestbuffers()
    req.count = 4
    req.type = V4L2_BUF_TYPE_VIDEO_OUTPUT
    req.memory = V4L2_MEMORY_MMAP
    
    try:
        fcntl.ioctl(fd, VIDIOC_REQBUFS, req)
    except Exception as e:
        print(f"Failed to request buffers: {e}")
        return None
        
    print(f"{req.count} buffers requested.")
    
    # Allocate buffer objects
    buffers = []
    for i in range(req.count):
        # Query each buffer
        buf = v4l2_buffer()
        buf.type = V4L2_BUF_TYPE_VIDEO_OUTPUT
        buf.memory = V4L2_MEMORY_MMAP
        buf.index = i
        
        try:
            fcntl.ioctl(fd, VIDIOC_QUERYBUF, buf)
        except Exception as e:
            print(f"Failed to query buffer {i}: {e}")
            return None
            
        # mmap the buffer
        try:
            mm = mmap.mmap(fd, buf.length, 
                          flags=mmap.MAP_SHARED,
                          prot=mmap.PROT_READ | mmap.PROT_WRITE,
                          offset=buf.m.offset)
                          
            print(f"Buffer {i}:")
            print(f"  Mapped at offset {buf.m.offset}")
            print(f"  Length: {buf.length}")
            print(f"  Memory map object: {mm}")
            
            buffers.append({
                'index': i,
                'length': buf.length,
                'mmap': mm,
                'start': mm
            })
        except Exception as e:
            print(f"Failed to mmap buffer {i}: {e}")
            # Clean up previously mapped buffers
            for b in buffers:
                b['mmap'].close()
            return None
    
    return buffers

def queue_initial_buffers(fd, buffers, width, height):
    """Queue initial buffers with test pattern"""
    for buf in buffers:
        # Fill buffer with test pattern
        bytes_used = generate_test_pattern(buf['mmap'], width, height)
        
        # Queue the buffer
        v4l2_buf = v4l2_buffer()
        v4l2_buf.type = V4L2_BUF_TYPE_VIDEO_OUTPUT
        v4l2_buf.memory = V4L2_MEMORY_MMAP
        v4l2_buf.index = buf['index']
        v4l2_buf.bytesused = bytes_used
        
        try:
            fcntl.ioctl(fd, VIDIOC_QBUF, v4l2_buf)
            print(f"Queued buffer {buf['index']}")
        except Exception as e:
            print(f"Failed to queue buffer {buf['index']}: {e}")
            return False
    return True

EVENT_HANDLERS = {
    UVC_EVENT_CONNECT: handle_connect_event,
    UVC_EVENT_DISCONNECT: handle_disconnect_event,
    UVC_EVENT_SETUP: handle_setup_event,
    UVC_EVENT_DATA: handle_data_event,
    UVC_EVENT_STREAMON: handle_streamon_event,
    UVC_EVENT_STREAMOFF: handle_streamoff_event,
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

def stream_on(fd):
    """Start video streaming"""
    buf_type = c_int32(V4L2_BUF_TYPE_VIDEO_OUTPUT)
    try:
        fcntl.ioctl(fd, VIDIOC_STREAMON, byref(buf_type))
        print("Stream ON successful")
        return True
    except Exception as e:
        print(f"Failed to start stream: {e}")
        return False

def stream_off(fd):
    """Stop video streaming"""
    buf_type = c_int32(V4L2_BUF_TYPE_VIDEO_OUTPUT)
    try:
        fcntl.ioctl(fd, VIDIOC_STREAMOFF, byref(buf_type))
        print("Stream OFF successful")
        return True
    except Exception as e:
        print(f"Failed to stop stream: {e}")
        return False

def handle_streamon_event(event):
    """Handle UVC_EVENT_STREAMON"""
    print("\nUVC_EVENT_STREAMON")
    global state
    
    try:
        # Start the video stream
        buf_type = c_int32(V4L2_BUF_TYPE_VIDEO_OUTPUT)
        print("Starting video stream...")
        fcntl.ioctl(fd, VIDIOC_STREAMON, buf_type)
        print("Stream started successfully")
        
        if not current_format or not buffers:
            print("Error: Missing format or buffers")
            return None
            
        print(f"\nCurrent format:")
        print(f"  Width: {current_format.width}")
        print(f"  Height: {current_format.height}")
        print(f"  Pixel format: {hex(current_format.pixelformat)}")
        print(f"  Bytes per line: {current_format.bytesperline}")
        print(f"  Size image: {current_format.sizeimage}")
            
        # Queue initial buffers
        for buf in buffers:
            print(f"\nProcessing buffer {buf['index']}:")
            
            # Fill buffer with test pattern
            bytes_used = generate_test_pattern(buf['mmap'], current_format.width, current_format.height)
            
            v4l2_buf = v4l2_buffer()
            v4l2_buf.type = V4L2_BUF_TYPE_VIDEO_OUTPUT
            v4l2_buf.memory = V4L2_MEMORY_MMAP
            v4l2_buf.index = buf['index']
            v4l2_buf.bytesused = bytes_used
            
            try:
                fcntl.ioctl(fd, VIDIOC_QBUF, v4l2_buf)
                print(f"  Successfully queued buffer {buf['index']}")
            except Exception as e:
                print(f"  Failed to queue buffer: {e}")
                print(f"  Error details: {type(e).__name__}")
        
        # Start streaming thread
        state.streaming = True
        print("\nStarting streaming thread...")
        import threading
        thread = threading.Thread(target=streaming_thread, daemon=True)
        thread.start()
        print("Streaming thread started with ID:", thread.ident)
            
    except Exception as e:
        print(f"Failed to start stream: {e}")
        print(f"Error details: {type(e).__name__}")
    
    return None

def handle_streamoff_event(event):
    """Handle UVC_EVENT_STREAMOFF"""
    print("Handling STREAMOFF event")
    return stream_off(fd)

if __name__ == "__main__":
    main()
