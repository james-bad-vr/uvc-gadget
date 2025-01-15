import fcntl
import os
import select
import errno
import sys

from ctypes import (
    Structure, Union, c_char, c_uint32, c_uint8, c_int32, c_uint16, c_long,
    sizeof, addressof, pointer, cast, POINTER, create_string_buffer,
    memmove, memset
)

print(f"System endianness: {sys.byteorder}")  # Outputs 'little' or 'big'
print(f"Size of usb_ctrlrequest: {sizeof(usb_ctrlrequest)}")

VIDIOC_SUBSCRIBE_EVENT = 0x4020565a
VIDIOC_DQEVENT = 0x80805659
VIDIOC_QUERYCAP = 0x80685600

UVCIOC_SEND_RESPONSE = 0x40087544

USB_TYPE_MASK = 0x60
USB_TYPE_STANDARD = 0x00
USB_TYPE_CLASS = 0x20

# UVC event types
V4L2_EVENT_PRIVATE_START = 0x08000000
UVC_EVENT_CONNECT    = V4L2_EVENT_PRIVATE_START + 0
UVC_EVENT_DISCONNECT = V4L2_EVENT_PRIVATE_START + 1
UVC_EVENT_STREAMON   = V4L2_EVENT_PRIVATE_START + 2
UVC_EVENT_STREAMOFF  = V4L2_EVENT_PRIVATE_START + 3
UVC_EVENT_SETUP      = V4L2_EVENT_PRIVATE_START + 4
UVC_EVENT_DATA       = V4L2_EVENT_PRIVATE_START + 5

class v4l2_event_subscription(Structure):
    _fields_ = [
        ('type', c_uint32),
        ('id', c_uint32),
        ('flags', c_uint32),
        ('reserved', c_uint32 * 5)
    ]

class v4l2_capability(Structure):
    _fields_ = [
        ("driver", c_char * 16),     # Driver name
        ("card", c_char * 32),       # Card name
        ("bus_info", c_char * 32),   # Bus information
        ("version", c_uint32),       # Driver version
        ("capabilities", c_uint32),  # Supported capabilities
        ("device_caps", c_uint32),   # Device-specific capabilities
        ("reserved", c_uint32 * 3)   # Reserved for future use
    ]

class usb_ctrlrequest(Structure):
    _fields_ = [
        ('bRequestType', c_uint8),  # 1 byte
        ('bRequest', c_uint8),      # 1 byte
        ('wValue', c_uint16),       # 2 bytes
        ('wIndex', c_uint16),       # 2 bytes
        ('wLength', c_uint16),      # 2 bytes
    ]

class uvc_request_data(Structure):
    _fields_ = [
        ('length', c_int32),
        ('data', c_uint8 * 60),
    ]
    def __init__(self):
        super().__init__()
        self.length = -errno.EL2HLT  # Set to -EL2HLT

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


def main():
    device_path = "/dev/video0"
    fd_raw = os.open(device_path, os.O_RDWR | os.O_NONBLOCK)
    
    cap = v4l2_capability();
    fcntl.ioctl(fd_raw, VIDIOC_QUERYCAP, cap)
    
    # Print the queried capabilities
    print(f"Driver: {cap.driver.decode('utf-8')}")
    print(f"Card: {cap.card.decode('utf-8')}")
    print(f"Bus Info: {cap.bus_info.decode('utf-8')}")
    print(f"Version: {cap.version}")
    print(f"Capabilities: 0x{cap.capabilities:08x}")
    print(f"Device Caps: 0x{cap.device_caps:08x}")
    print("")

    subscribe_event(fd_raw, UVC_EVENT_CONNECT)
    subscribe_event(fd_raw, UVC_EVENT_DISCONNECT)
    subscribe_event(fd_raw, UVC_EVENT_SETUP)
    subscribe_event(fd_raw, UVC_EVENT_DATA)
    subscribe_event(fd_raw, UVC_EVENT_STREAMON)
    subscribe_event(fd_raw, UVC_EVENT_STREAMOFF)
    
    epoll = select.epoll()
    epoll.register(fd_raw, select.EPOLLPRI)
    
    event = v4l2_event()
    i = 0

    try:
        while True:
            events = epoll.poll(1)  # 1-second timeout
            for fd, event_mask in events:
                i += 1
                fcntl.ioctl(fd, VIDIOC_DQEVENT, event)
                handler = EVENT_HANDLERS.get(event.type)
                response = handler(event)
                if (response):
                    fcntl.ioctl(fd, UVCIOC_SEND_RESPONSE, response)
                
                
    except KeyboardInterrupt:
        print("\nExiting...")
    finally:
        epoll.unregister(fd_raw)
        epoll.close()
        os.close(fd_raw)

def subscribe_event(fd, typ):
    sub = v4l2_event_subscription(type=typ)
    
    try:
        fcntl.ioctl(fd, VIDIOC_SUBSCRIBE_EVENT, sub)
        #print(f"subscribed to {typ}")
    except Exception as e:
        print(f"Failed to subscribe to events: {e}")


def handle_connect_event(event):
    print("UVC_EVENT_CONNECT")
    # Add logic for handling connect event
    return None

def handle_disconnect_event(event):
    print("UVC_EVENT_DISCONNECT")
    # Add logic for handling disconnect event
    return None

def handle_streamon_event(event):
    print("UVC_EVENT_STREAMON")
    # Add logic for handling stream on event
    return None

def handle_streamoff_event(event):
    print("UVC_EVENT_STREAMOFF")
    # Add logic for handling stream off event
    return None

def handle_setup_event(event):
    print("UVC_EVENT_SETUP")
    
    req = event.u.req
    print(f"    bRequestType: 0x{req.bRequestType:02x}")
    print(f"    bReques:      0x{req.bRequest:02x}")
    print(f"    wValue:       0x{req.wValue:04x}")
    print(f"    wIndex:       0x{req.wIndex:04x}")
    print(f"    wLength       0x{req.wLength:04x}")
    
    if (req.bRequestType & USB_TYPE_MASK == USB_TYPE_STANDARD):
        print("  USB standard request")
    elif (req.bRequestType & USB_TYPE_MASK == USB_TYPE_CLASS):
        print("  USB process class")
    
    cs = (req.wValue >> 8) & 0xFF
    print(f"  Control Selector: 0x{cs:02x}")
    
    response = uvc_request_data()
    return response

def handle_data_event(event, response):
    print("  Event: UVC_EVENT_DATA")
    req_data = event.u.data
    print(f"    Data length: {req_data.length}")
    print(f"    Data: {bytes(req_data.data[:req_data.length])}")
    # Add logic for handling data event
    return None

EVENT_HANDLERS = {
    UVC_EVENT_CONNECT: handle_connect_event,
    UVC_EVENT_DISCONNECT: handle_disconnect_event,
    UVC_EVENT_STREAMON: handle_streamon_event,
    UVC_EVENT_STREAMOFF: handle_streamoff_event,
    UVC_EVENT_SETUP: handle_setup_event,
    UVC_EVENT_DATA: handle_data_event,
}

if __name__ == "__main__":
    main()