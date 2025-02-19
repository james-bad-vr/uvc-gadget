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

# Add these constants at the top with your other constants
UVC_RC_UNDEFINED = 0x00
UVC_SET_CUR = 0x01
UVC_GET_CUR = 0x81
UVC_GET_MIN = 0x82
UVC_GET_MAX = 0x83
UVC_GET_RES = 0x84
UVC_GET_LEN = 0x85
UVC_GET_INFO = 0x86
UVC_GET_DEF = 0x87

# Add this lookup table and function
UVC_REQUEST_NAMES = {
    UVC_RC_UNDEFINED: "UNDEFINED",
    UVC_SET_CUR: "SET_CUR",
    UVC_GET_CUR: "GET_CUR",
    UVC_GET_MIN: "GET_MIN",
    UVC_GET_MAX: "GET_MAX",
    UVC_GET_RES: "GET_RES",
    UVC_GET_LEN: "GET_LEN",
    UVC_GET_INFO: "GET_INFO",
    UVC_GET_DEF: "GET_DEF",
}



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

def uvc_request_name(req):
    """Convert a UVC request code to a readable string"""
    return UVC_REQUEST_NAMES.get(req, "UNKNOWN")

def init_streaming_control(ctrl, mode='default'):
    """Initialize streaming control with exact same values as C code"""
    ctrl.bmHint = 1
    ctrl.bFormatIndex = 1
    ctrl.bFrameIndex = 1
    
    # Set frame interval based on mode
    if mode == 'min':
        ctrl.dwFrameInterval = 500000  # Slowest frame rate
    elif mode == 'max':
        ctrl.dwFrameInterval = 166666  # Fastest frame rate
    else:
        ctrl.dwFrameInterval = 333333  # Default 30fps
        
    ctrl.wKeyFrameRate = 0
    ctrl.wPFrameRate = 0
    ctrl.wCompQuality = 0
    ctrl.wCompWindowSize = 0
    ctrl.wDelay = 0
    ctrl.dwMaxVideoFrameSize = 640 * 360 * 2
    ctrl.dwMaxPayloadTransferSize = 2048  # Match C code exactly
    ctrl.dwClockFrequency = 48000000
    ctrl.bmFramingInfo = 3
    ctrl.bPreferedVersion = 1
    ctrl.bMinVersion = 1
    ctrl.bMaxVersion = 1


def set_video_format(fd):
    """Set video format to YUYV 640x360"""
    print("\nSetting video format")
    global current_format
    
    fmt = v4l2_format()
    fmt.type = V4L2_BUF_TYPE_VIDEO_OUTPUT
    fmt.fmt.pix.width = 640
    fmt.fmt.pix.height = 360
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
    elif req.bRequest == UVC_GET_RES:
        print("-> GET_RES request")
        temp_ctrl = uvc_streaming_control()
        init_streaming_control(temp_ctrl)
        memmove(addressof(response.data), addressof(temp_ctrl), sizeof(uvc_streaming_control))
        response.length = sizeof(uvc_streaming_control)
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
        
        # Set frame rate to 30 fps (or desired rate)
        fps = 30
        frame_interval = int(1000000000 / fps)  # Convert to nanoseconds
        print(f"\nSetting frame rate to {fps} fps (interval: {frame_interval}ns)")
        
        # Queue initial buffers with timing information
        for buf in buffers:
            print(f"\nProcessing buffer {buf['index']}:")
            
            # Fill buffer with test pattern
            bytes_used = generate_test_pattern(
                buf['mmap'], 
                current_format.width, 
                current_format.height
            )
            
            v4l2_buf = v4l2_buffer()
            v4l2_buf.type = V4L2_BUF_TYPE_VIDEO_OUTPUT
            v4l2_buf.memory = V4L2_MEMORY_MMAP
            v4l2_buf.index = buf['index']
            v4l2_buf.bytesused = bytes_used
            v4l2_buf.timestamp.tv_sec = 0
            v4l2_buf.timestamp.tv_usec = 0  # Let kernel set timestamp
            
            try:
                fcntl.ioctl(fd, VIDIOC_QBUF, v4l2_buf)
                print(f"  Successfully queued buffer {buf['index']}")
            except Exception as e:
                print(f"  Failed to queue buffer: {e}")
                print(f"  Error details: {type(e).__name__}")
        
        # Start streaming thread with timing control
        state.streaming = True
        print("\nStarting streaming thread...")
        import threading
        thread = threading.Thread(target=streaming_thread, args=(fps,), daemon=True)
        thread.start()
        print("Streaming thread started with ID:", thread.ident)
            
    except Exception as e:
        print(f"Failed to start stream: {e}")
        print(f"Error details: {type(e).__name__}")
    
    return None

def streaming_thread(fps):
    """Background thread to handle continuous streaming with proper timing"""
    print("\nStreaming thread started")
    frame_count = 0
    pattern_index = 0  # Track which pattern we're using
    start_time = time.time()
    
    # Create a poll object for monitoring buffer availability
    poll = select.epoll()
    poll.register(fd, select.EPOLLOUT)
    
    # Stats tracking
    last_stats_time = time.time()
    frames_since_stats = 0
    
    while state.streaming:
        try:
            current_time = time.time()
            
            # Print stats only once per second
            if current_time - last_stats_time >= 1.0:
                actual_fps = frames_since_stats / (current_time - last_stats_time)
                print(f"FPS: {actual_fps:.1f}, Frames: {frame_count}")
                last_stats_time = current_time
                frames_since_stats = 0
            
            # Wait for buffer
            events = poll.poll(10)  # 10ms timeout
            if not events:
                continue
            
            # Dequeue buffer
            buf = v4l2_buffer()
            buf.type = V4L2_BUF_TYPE_VIDEO_OUTPUT
            buf.memory = V4L2_MEMORY_MMAP
            
            try:
                fcntl.ioctl(fd, VIDIOC_DQBUF, buf)
            except OSError as e:
                if e.errno == errno.EAGAIN:
                    continue
                raise
            
            buffer = buffers[buf.index]
            
            # Write next pattern
            buffer['mmap'].seek(0)
            buffer['mmap'].write(buffer['patterns'][pattern_index])
            
            # Move to next pattern
            pattern_index = (pattern_index + 1) % 8
            
             # Ensure proper buffer size
            buffer_size = current_format.width * current_format.height * 2
            buf.bytesused = buffer_size  # Set exact size
            buf.timestamp.tv_sec = int(current_time)
            buf.timestamp.tv_usec = int((current_time - int(current_time)) * 1000000)
            
            try:
                fcntl.ioctl(fd, VIDIOC_QBUF, buf)
                frame_count += 1
                frames_since_stats += 1
            except OSError as e:
                if e.errno != errno.EAGAIN:
                    raise
                    
        except Exception as e:
            if not state.streaming:
                break
            print(f"Streaming error: {e}")
            break
            
    poll.unregister(fd)
    poll.close()
    print(f"Streaming ended - Average FPS: {frame_count / (time.time() - start_time):.1f}")

def generate_test_pattern(mm, width, height, offset=0):
    """Optimized test pattern generation with explicit buffer layout"""
    stride = width * 2  # YUY2 is 2 bytes per pixel
    total_size = stride * height
    pattern = bytearray(total_size)
    
    # Fill pattern line by line with proper stride
    for y in range(height):
        row_offset = y * stride
        for x in range(0, stride, 4):  # Process 2 pixels (4 bytes) at a time
            pixel_x = x // 2
            shifted_x = (pixel_x + offset) % width
            # Checkerboard based on coordinates
            is_white = ((y // 64) + (shifted_x // 64)) % 2 == 0
            
            # YUY2 pattern: Y1 U Y2 V
            if is_white:
                # White in YUV space
                pattern[row_offset + x:row_offset + x + 4] = bytes([235, 128, 235, 128])
            else:
                # Gray in YUV space
                pattern[row_offset + x:row_offset + x + 4] = bytes([128, 128, 128, 128])

    mm.seek(0)
    mm.write(bytes(pattern))
    return total_size

def handle_streamoff_event(event):
    """Handle UVC_EVENT_STREAMOFF"""
    print("Handling STREAMOFF event")
    try:
        buf_type = c_uint32(V4L2_BUF_TYPE_VIDEO_OUTPUT)
        fcntl.ioctl(fd, VIDIOC_STREAMOFF, buf_type)
        state.streaming = False
        print("Stream stopped successfully")
    except Exception as e:
        print(f"Failed to stop stream: {e}")
    return None

def handle_setup_event(event):
    print("\n" + "="*50)
    print("UVC_EVENT_SETUP")
    print("="*50)
    
    # Log raw event data
    print("Raw event data (first 16 bytes):")
    raw_data = bytes(event.u.data.data[:16])
    print(' '.join(f'{b:02x}' for b in raw_data))
    
    # Parse request
    req = usb_ctrlrequest.from_buffer_copy(bytes(event.u.data.data[:8]))
    response = uvc_request_data()
    response.length = -errno.EL2HLT
    
    # Log request details
    print("\nRequest Details:")
    print(f"  bmRequestType: 0x{req.bRequestType:02x}")
    print(f"  bRequest:      0x{req.bRequest:02x} ({uvc_request_name(req.bRequest)})")
    print(f"  wValue:        0x{req.wValue:04x}")
    print(f"  wIndex:        0x{req.wIndex:04x}")
    print(f"  wLength:       {req.wLength}")
    
    # Parse request type
    request_type = req.bRequestType & USB_TYPE_MASK
    print(f"\nRequest Type: 0x{request_type:02x} " + 
          f"({'Class' if request_type == USB_TYPE_CLASS else 'Standard'})")
    
    # Check if it's a class request
    if request_type == USB_TYPE_CLASS:
        cs = (req.wValue >> 8) & 0xFF
        interface = req.wIndex & 0xFF
        
        print(f"\nClass-specific request:")
        print(f"  Control Selector: 0x{cs:02x}")
        print(f"  Interface:        {interface}")
        
        # Handle control interface requests (interface 0)
        if interface == 0:
            print("\nHandling Control Interface Request")
            # Always return 0x03 for GET_INFO (indicating GET/SET supported)
            response.data[0] = 0x03
            response.length = req.wLength
            
        # Handle streaming interface requests (interface 1)
        elif interface == 1:
            print("\nHandling Streaming Interface Request")
            
            if cs in [UVC_VS_PROBE_CONTROL, UVC_VS_COMMIT_CONTROL]:
                print(f"  Control: {'PROBE' if cs == UVC_VS_PROBE_CONTROL else 'COMMIT'}")
                ctrl = state.probe_control if cs == UVC_VS_PROBE_CONTROL else state.commit_control
                  # Add explicit size calculations
                ctrl.dwMaxVideoFrameSize = current_format.width * current_format.height * 2
                ctrl.bmHint = 1
                ctrl.bFormatIndex = 1
                ctrl.bFrameIndex = 1
                
                # Ensure proper stride alignment for macOS
                ctrl.wWidth = current_format.width
                ctrl.wHeight = current_format.height
                ctrl.dwMinBitRate = current_format.width * current_format.height * 16
                ctrl.dwMaxBitRate = current_format.width * current_format.height * 16
                
                if req.bRequest == UVC_SET_CUR:
                    print("  Operation: SET_CUR")
                    print("  -> Setting current_control and preparing for DATA phase")
                    state.current_control = cs
                    response.length = 34  # Match C code exactly
                    
                elif req.bRequest == UVC_GET_CUR:
                    print("  Operation: GET_CUR")
                    print("  -> Returning current control values")
                    memmove(addressof(response.data), addressof(ctrl), 
                           sizeof(uvc_streaming_control))
                    response.length = sizeof(uvc_streaming_control)
                    
                elif req.bRequest == UVC_GET_MIN:
                    print("  Operation: GET_MIN")
                    print("  -> Returning minimum supported values")
                    temp_ctrl = uvc_streaming_control()
                    init_streaming_control(temp_ctrl, mode='min')
                    memmove(addressof(response.data), addressof(temp_ctrl),
                           sizeof(uvc_streaming_control))
                    response.length = sizeof(uvc_streaming_control)
                    
                elif req.bRequest == UVC_GET_MAX:
                    print("  Operation: GET_MAX")
                    print("  -> Returning maximum supported values")
                    temp_ctrl = uvc_streaming_control()
                    init_streaming_control(temp_ctrl, mode='max')
                    memmove(addressof(response.data), addressof(temp_ctrl),
                           sizeof(uvc_streaming_control))
                    response.length = sizeof(uvc_streaming_control)
                    
                elif req.bRequest == UVC_GET_RES:
                    print("  Operation: GET_RES")
                    print("  -> Returning resolution values")
                    temp_ctrl = uvc_streaming_control()
                    init_streaming_control(temp_ctrl)
                    memmove(addressof(response.data), addressof(temp_ctrl),
                           sizeof(uvc_streaming_control))
                    response.length = sizeof(uvc_streaming_control)
                    
                elif req.bRequest == UVC_GET_INFO:
                    print("  Operation: GET_INFO")
                    print("  -> Returning capabilities (0x03: GET/SET supported)")
                    response.data[0] = 0x03
                    response.length = 1
                    
                elif req.bRequest == UVC_GET_DEF:
                    print("  Operation: GET_DEF")
                    print("  -> Returning default values")
                    temp_ctrl = uvc_streaming_control()
                    init_streaming_control(temp_ctrl)
                    memmove(addressof(response.data), addressof(temp_ctrl),
                           sizeof(uvc_streaming_control))
                    response.length = sizeof(uvc_streaming_control)
        
    print(f"\nResponse prepared:")
    print(f"  Length: {response.length}")
    if response.length > 0:
        print("  Data (first 16 bytes):")
        resp_data = bytes(response.data[:min(16, response.length)])
        print('  ' + ' '.join(f'{b:02x}' for b in resp_data))
    
    print("="*50 + "\n")
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
    
    # Pre-generate 8 patterns with different offsets
    patterns = []
    for i in range(8):
        pattern = bytearray()
        bytes_per_line = current_format.width * 2
        square_size = 64
        offset = (i * current_format.width) // 8  # Divide width into 8 steps
        
        for y in range(current_format.height):
            for x in range(0, bytes_per_line, 4):
                pixel_x = x // 2
                shifted_x = (pixel_x + offset) % current_format.width
                is_white = ((y // square_size) + (shifted_x // square_size)) % 2 == 0
                color = WHITE if is_white else GRAY
                pattern.extend(color.to_bytes(4, byteorder='little'))
        
        patterns.append(bytes(pattern))
    
    print(f"Generated {len(patterns)} patterns")
    
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
            
            # Write initial pattern
            mm.seek(0)
            mm.write(patterns[0])
            
            buffers.append({
                'index': i,
                'length': buf.length,
                'mmap': mm,
                'start': mm,
                'pattern_size': len(patterns[0]),
                'patterns': patterns  # Store all patterns with the buffer
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
        
        # Set frame rate to 30 fps (or desired rate)
        fps = 30
        frame_interval = int(1000000000 / fps)  # Convert to nanoseconds
        print(f"\nSetting frame rate to {fps} fps (interval: {frame_interval}ns)")
        
        # Queue initial buffers with timing information
        for buf in buffers:
            print(f"\nProcessing buffer {buf['index']}:")
            
            # Fill buffer with test pattern
            bytes_used = generate_test_pattern(
                buf['mmap'], 
                current_format.width, 
                current_format.height
            )
            
            v4l2_buf = v4l2_buffer()
            v4l2_buf.type = V4L2_BUF_TYPE_VIDEO_OUTPUT
            v4l2_buf.memory = V4L2_MEMORY_MMAP
            v4l2_buf.index = buf['index']
            v4l2_buf.bytesused = bytes_used
            v4l2_buf.timestamp.tv_sec = 0
            v4l2_buf.timestamp.tv_usec = 0  # Let kernel set timestamp
            
            try:
                fcntl.ioctl(fd, VIDIOC_QBUF, v4l2_buf)
                print(f"  Successfully queued buffer {buf['index']}")
            except Exception as e:
                print(f"  Failed to queue buffer: {e}")
                print(f"  Error details: {type(e).__name__}")
        
        # Start streaming thread with timing control
        state.streaming = True
        print("\nStarting streaming thread...")
        import threading
        thread = threading.Thread(target=streaming_thread, args=(fps,), daemon=True)
        thread.start()
        print("Streaming thread started with ID:", thread.ident)
            
    except Exception as e:
        print(f"Failed to start stream: {e}")
        print(f"Error details: {type(e).__name__}")
    
    return None

def streaming_thread(fps):
    """Background thread to handle continuous streaming with proper timing"""
    print("\nStreaming thread started")
    print(f"Current format:")
    print(f"  Width: {current_format.width}")
    print(f"  Height: {current_format.height}")
    print(f"  Bytes per line: {current_format.bytesperline}")
    print(f"  Size image: {current_format.sizeimage}")
    print(f"  Actual buffer size being used: {buffers[0]['length']}")
    frame_count = 0
    pattern_index = 0  # Track which pattern we're using
    start_time = time.time()
    
    # Create a poll object for monitoring buffer availability
    poll = select.epoll()
    poll.register(fd, select.EPOLLOUT)
    
    # Stats tracking
    last_stats_time = time.time()
    frames_since_stats = 0
    
    while state.streaming:
        try:
            current_time = time.time()
            
            # Print stats only once per second
            if current_time - last_stats_time >= 1.0:
                actual_fps = frames_since_stats / (current_time - last_stats_time)
                print(f"FPS: {actual_fps:.1f}, Frames: {frame_count}")
                last_stats_time = current_time
                frames_since_stats = 0
            
            # Wait for buffer
            events = poll.poll(10)  # 10ms timeout
            if not events:
                continue
            
            # Dequeue buffer
            buf = v4l2_buffer()
            buf.type = V4L2_BUF_TYPE_VIDEO_OUTPUT
            buf.memory = V4L2_MEMORY_MMAP
            
            try:
                fcntl.ioctl(fd, VIDIOC_DQBUF, buf)
            except OSError as e:
                if e.errno == errno.EAGAIN:
                    continue
                raise
            
            buffer = buffers[buf.index]
            
            # Write next pattern
            buffer['mmap'].seek(0)
            buffer['mmap'].write(buffer['patterns'][pattern_index])
            
            # Move to next pattern
            pattern_index = (pattern_index + 1) % 8
            
            # Queue buffer back
            buf.bytesused = buffer['pattern_size']
            buf.timestamp.tv_sec = int(current_time)
            buf.timestamp.tv_usec = int((current_time - int(current_time)) * 1000000)
            
            try:
                fcntl.ioctl(fd, VIDIOC_QBUF, buf)
                frame_count += 1
                frames_since_stats += 1
            except OSError as e:
                if e.errno != errno.EAGAIN:
                    raise
                    
        except Exception as e:
            if not state.streaming:
                break
            print(f"Streaming error: {e}")
            break
            
    poll.unregister(fd)
    poll.close()
    print(f"Streaming ended - Average FPS: {frame_count / (time.time() - start_time):.1f}")

def generate_test_pattern(mm, width, height, offset=0):
    """Optimized test pattern generation"""
    bytes_per_line = width * 2
    total_size = bytes_per_line * height
    pattern = bytearray(total_size)  # Pre-allocate full buffer
    square_size = 64
    horizontal_offset = offset % width
    
    for y in range(height):
        line_offset = y * bytes_per_line
        for x in range(0, bytes_per_line, 4):
            pixel_x = x // 2
            shifted_x = (pixel_x + offset) % width
            is_white = ((y // 64) + (shifted_x // 64)) % 2 == 0
            color = WHITE if is_white else GRAY
            pattern[line_offset + x:line_offset + x + 4] = color.to_bytes(4, byteorder='little')

    mm.seek(0)
    mm.write(bytes(pattern))
    return total_size  # Return exact buffer size

def handle_streamoff_event(event):
    """Handle UVC_EVENT_STREAMOFF"""
    print("Handling STREAMOFF event")
    return stream_off(fd)

def process_frame(mm, width, height, frame_count):
    """Process a single frame with proper timing"""
    offset = frame_count % width  # Create movement effect
    bytes_written = generate_test_pattern(mm, width, height, offset)
    print(f"\nProcessing buffer {frame_count % 4}:")  # Assuming 4 buffers
    return bytes_written

def stream_video(fd, width, height, fps):
    """Stream video with proper timing"""
    frame_count = 0
    interval = 1.0 / fps  # Calculate interval between frames
    next_frame_time = time.time()

    while True:
        try:
            current_time = time.time()
            if current_time >= next_frame_time:
                # Process and queue the next frame
                process_frame(mm, width, height, frame_count)
                frame_count += 1
                next_frame_time = current_time + interval
                
                # Sleep for a small amount to prevent CPU spinning
                sleep_time = max(0, next_frame_time - time.time())
                if sleep_time > 0:
                    time.sleep(sleep_time)
            else:
                # Small sleep to prevent CPU spinning while waiting
                time.sleep(0.001)
                
        except Exception as e:
            print(f"Error in streaming loop: {e}")
            break

if __name__ == "__main__":
    main()
