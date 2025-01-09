#!/usr/bin/env python3
import fcntl
import struct
import os
import time
import select
from ctypes import (
    Structure, Union, c_uint32, c_uint8, c_long, c_int32, c_uint16,
    sizeof, addressof, pointer, cast, POINTER, create_string_buffer,
    memmove, memset
)

# IOCTL codes
VIDIOC_SUBSCRIBE_EVENT = 0x4020565a
VIDIOC_DQEVENT = 0x80805659
UVCIOC_SEND_RESPONSE = 0x40087544

# UVC event types (from g_uvc.h)
V4L2_EVENT_PRIVATE_START = 0x08000000
UVC_EVENT_CONNECT    = V4L2_EVENT_PRIVATE_START + 0
UVC_EVENT_DISCONNECT = V4L2_EVENT_PRIVATE_START + 1
UVC_EVENT_STREAMON   = V4L2_EVENT_PRIVATE_START + 2
UVC_EVENT_STREAMOFF  = V4L2_EVENT_PRIVATE_START + 3
UVC_EVENT_SETUP      = V4L2_EVENT_PRIVATE_START + 4
UVC_EVENT_DATA       = V4L2_EVENT_PRIVATE_START + 5

# UVC control selectors (from USB Video Class spec)
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
    _pack_ = 1  # Important! Matches kernel structure packing
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
        # Additional fields might be needed
    ]

class uvc_event(Union):
    _fields_ = [
        ('speed', c_uint32),       # enum usb_device_speed
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

# Global state
probe_control = uvc_streaming_control()
commit_control = uvc_streaming_control()
current_control = None

def init_streaming_control(ctrl):
    """Initialize a streaming control structure with default values"""
    ctrl.bmHint = 1
    ctrl.bFormatIndex = 1
    ctrl.bFrameIndex = 1
    ctrl.dwFrameInterval = 333333  # 30 fps (1/30 = 0.033s = 33333.3us)
    ctrl.wKeyFrameRate = 0
    ctrl.wPFrameRate = 0
    ctrl.wCompQuality = 0
    ctrl.wCompWindowSize = 0
    ctrl.wDelay = 0
    ctrl.dwMaxVideoFrameSize = 640 * 360 * 2  # YUY2 format
    ctrl.dwMaxPayloadTransferSize = 3072
    ctrl.dwClockFrequency = 48000000
    ctrl.bmFramingInfo = 3
    ctrl.bPreferedVersion = 1
    ctrl.bMinVersion = 1
    ctrl.bMaxVersion = 1

def copy_streaming_control(dest, src):
    """Copy streaming control data from src to dest"""
    memmove(addressof(dest), addressof(src), sizeof(uvc_streaming_control))

def handle_setup_event(fd, event):
    global current_control, probe_control, commit_control
    
    req = event.u.req
    print(f"Setup Request:")
    print(f"  bmRequestType: 0x{req.bRequestType:02x}")
    print(f"  bRequest: 0x{req.bRequest:02x}")
    print(f"  wValue: 0x{req.wValue:04x}")
    print(f"  wIndex: 0x{req.wIndex:04x}")
    print(f"  wLength: {req.wLength}")

    response = uvc_request_data()
    response.length = -1  # Default to no response

    # Extract control selector from wValue high byte
    cs = (req.wValue >> 8) & 0xFF
    print(f"  Control Selector: 0x{cs:02x}")

    if req.bRequestType == 0xA1:  # Class-specific GET request
        if cs == UVC_VS_PROBE_CONTROL or cs == UVC_VS_COMMIT_CONTROL:
            ctrl = probe_control if cs == UVC_VS_PROBE_CONTROL else commit_control
            
            if req.bRequest == UVC_GET_INFO:
                print("  -> GET_INFO request")
                response.data[0] = 0x03  # GET/SET supported
                response.length = 1
            elif req.bRequest == UVC_GET_LEN:
                print("  -> GET_LEN request")
                response.data[0] = 0x22  # 34 bytes (sizeof(uvc_streaming_control))
                response.data[1] = 0x00
                response.length = 2
            elif req.bRequest == UVC_GET_CUR:
                print("  -> GET_CUR request")
                # Copy current control settings
                memmove(addressof(response.data), addressof(ctrl), sizeof(uvc_streaming_control))
                response.length = sizeof(uvc_streaming_control)
            elif req.bRequest in (UVC_GET_MIN, UVC_GET_MAX, UVC_GET_DEF):
                print(f"  -> GET_{['MIN', 'MAX', 'DEF'][req.bRequest - 0x82]} request")
                # Set default streaming parameters
                temp_ctrl = uvc_streaming_control()
                init_streaming_control(temp_ctrl)
                memmove(addressof(response.data), addressof(temp_ctrl), sizeof(uvc_streaming_control))
                response.length = sizeof(uvc_streaming_control)
    
    elif req.bRequestType == 0x21:  # Class-specific SET request
        if cs == UVC_VS_PROBE_CONTROL or cs == UVC_VS_COMMIT_CONTROL:
            if req.bRequest == UVC_SET_CUR:
                print(f"  -> SET_CUR request for {'PROBE' if cs == UVC_VS_PROBE_CONTROL else 'COMMIT'}")
                current_control = cs
                response.length = sizeof(uvc_streaming_control)
    
    if response.length > 0:
        try:
            fcntl.ioctl(fd, UVCIOC_SEND_RESPONSE, response)
            print("  -> Response sent successfully")
            print(f"  -> Response length: {response.length}")
            if response.length <= 4:  # Only print small responses in full
                print(f"  -> Response data: {' '.join(f'{b:02x}' for b in bytes(response.data)[:response.length])}")
            else:
                print(f"  -> Response data first 4 bytes: {' '.join(f'{b:02x}' for b in bytes(response.data)[:4])}")
        except Exception as e:
            print(f"  -> Failed to send response: {e}")
            print(f"  -> Response buffer: {bytes(response.data)[:16].hex()}")

def handle_data_event(event):
    global current_control, probe_control, commit_control
    
    print("Data event received")
    if current_control is None:
        print("Warning: No current control set for data event")
        return
        
    data_len = event.u.data.length
    if data_len > sizeof(uvc_streaming_control):
        print(f"Warning: Data length {data_len} exceeds streaming control size {sizeof(uvc_streaming_control)}")
        data_len = sizeof(uvc_streaming_control)
    
    if current_control == UVC_VS_PROBE_CONTROL:
        print("Updating probe control")
        memmove(addressof(probe_control), event.u.data.data, data_len)
        dump_streaming_control("Probe", probe_control)
    elif current_control == UVC_VS_COMMIT_CONTROL:
        print("Updating commit control")
        memmove(addressof(commit_control), event.u.data.data, data_len)
        dump_streaming_control("Commit", commit_control)
    
    current_control = None

def dump_streaming_control(name, ctrl):
    """Debug function to print streaming control contents"""
    print(f"{name} Control Values:")
    print(f"  bmHint: 0x{ctrl.bmHint:04x}")
    print(f"  Format/Frame: {ctrl.bFormatIndex}/{ctrl.bFrameIndex}")
    print(f"  Interval: {ctrl.dwFrameInterval} ({1e7/ctrl.dwFrameInterval if ctrl.dwFrameInterval else 0:.2f} fps)")
    print(f"  Max Frame Size: {ctrl.dwMaxVideoFrameSize}")
    print(f"  Max Payload: {ctrl.dwMaxPayloadTransferSize}")

def subscribe_event(fd, event_type):
    sub = v4l2_event_subscription()
    # Zero out the entire structure
    memset(addressof(sub), 0, sizeof(sub))
    sub.type = event_type
    
    try:
        fcntl.ioctl(fd, VIDIOC_SUBSCRIBE_EVENT, sub)
        print(f"Subscribed to event 0x{event_type:08x}")
        # Debug output
        sub_bytes = bytes(sub)
        print(f"Subscription data: {' '.join(f'{b:02x}' for b in sub_bytes[:16])}")
    except Exception as e:
        print(f"Failed to subscribe to event 0x{event_type:08x}: {e}")
        raise

def handle_event(fd):
    event = v4l2_event()
    try:
        fcntl.ioctl(fd, VIDIOC_DQEVENT, event)
        
        print(f"\nEvent received:")
        print(f"  Type: 0x{event.type:08x}")
        print(f"  Sequence: {event.sequence}")
        print(f"  Pending: {event.pending}")
        
        if event.type == UVC_EVENT_SETUP:
            handle_setup_event(fd, event)
        elif event.type == UVC_EVENT_DATA:
            handle_data_event(event)
        elif event.type == UVC_EVENT_STREAMON:
            print("Stream ON event received")
        elif event.type == UVC_EVENT_STREAMOFF:
            print("Stream OFF event received")
        elif event.type == UVC_EVENT_CONNECT:
            print("Connect event received")
            # Initialize control structures
            init_streaming_control(probe_control)
            init_streaming_control(commit_control)
        elif event.type == UVC_EVENT_DISCONNECT:
            print("Disconnect event received")
        elif event.type == 0:
            print("Warning: Received event with type 0")
            print("Event memory:")
            event_bytes = bytes(event)[:128]
            for i in range(0, len(event_bytes), 16):
                print(f"  {' '.join(f'{b:02x}' for b in event_bytes[i:i+16])}")
            
    except Exception as e:
        print(f"Error handling event: {e}")
        print(f"Error details: {e!r}")
        print(f"Event structure size: {sizeof(event)}")
        print("Event memory:")
        event_bytes = bytes(event)[:128]
        for i in range(0, len(event_bytes), 16):
            print(f"  {' '.join(f'{b:02x}' for b in event_bytes[i:i+16])}")

def main():
    try:
        device_path = "/dev/video0"
        print(f"Opening {device_path}")
        fd = os.open(device_path, os.O_RDWR | os.O_NONBLOCK)
        
        # Subscribe to all valid events
        event_types = [
            UVC_EVENT_SETUP,
            UVC_EVENT_DATA,
            UVC_EVENT_STREAMON,
            UVC_EVENT_STREAMOFF,
            UVC_EVENT_CONNECT,
            UVC_EVENT_DISCONNECT
        ]
        
        for event_type in event_types:
            subscribe_event(fd, event_type)

        print("\nDevice ready - waiting for events...")
        print(f"Structure sizes:")
        print(f"  v4l2_event: {sizeof(v4l2_event)}")
        print(f"  uvc_event: {sizeof(uvc_event)}")
        print(f"  uvc_request_data: {sizeof(uvc_request_data)}")
        print(f"  usb_ctrlrequest: {sizeof(usb_ctrlrequest)}")
        print(f"  uvc_streaming_control: {sizeof(uvc_streaming_control)}")
        
        poll = select.poll()
        # Use POLLPRI for exception-style events only
        poll.register(fd, select.POLLPRI)
        
        while True:
            events = poll.poll(1000)
            if events:
                for fd, event_mask in events:
                    print(f"\nPoll event received - mask: 0x{event_mask:04x}")
                    handle_event(fd)
            else:
                # Optional: print a dot to show we're still running
                print(".", end="", flush=True)

            time.sleep(0.01)  # Small sleep to prevent busy-waiting

    except KeyboardInterrupt:
        print("\nExiting...")
    finally:
        if 'fd' in locals():
            os.close(fd)
            print("Device closed")

if __name__ == "__main__":
    main()