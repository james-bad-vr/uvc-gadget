#!/usr/bin/env python3
import fcntl
import struct
import os
import time
import select

# V4L2 and UVC constants
VIDIOC_SUBSCRIBE_EVENT = 0x4020565a
VIDIOC_DQEVENT = 0x8010565d
UVCIOC_SEND_RESPONSE = 0x40087544  # From uvcvideo.h

# UVC event types
UVC_EVENT_SETUP = 0x08000004
UVC_EVENT_DATA = 0x08000005
UVC_EVENT_STREAMON = 0x08000002
UVC_EVENT_STREAMOFF = 0x08000003

def subscribe_event(fd, event_type):
    data = struct.pack('IIIi16s', 
        event_type,  # type
        0,          # id
        0,          # flags
        0,          # reserved[0]
        b'\0' * 16  # remaining reserved bytes
    )
    fcntl.ioctl(fd, VIDIOC_SUBSCRIBE_EVENT, data)

def send_response(fd, data):
    try:
        fcntl.ioctl(fd, UVCIOC_SEND_RESPONSE, data)
    except Exception as e:
        print(f"Error sending response: {e}")

def handle_setup_event(fd, event_data):
    # Parse the setup request from the event data
    # The event data contains the USB setup packet starting at offset 4
    setup_data = event_data[4:12]  # 8 bytes of setup data
    bmRequestType, bRequest, wValue, wIndex, wLength = struct.unpack('<BBHHHH', setup_data)
    
    print(f"Setup Request: bmRequestType={hex(bmRequestType)} bRequest={hex(bRequest)} "
          f"wValue={hex(wValue)} wIndex={hex(wIndex)} wLength={hex(wLength)}")

    # Prepare response
    # Default response for most setup packets
    response_data = struct.pack('i124s', 0, b'\0' * 124)  # 128 bytes total
    send_response(fd, response_data)

def handle_event(fd):
    # Create buffer for v4l2_event (96 bytes)
    event_buf = bytearray(96)
    
    try:
        fcntl.ioctl(fd, VIDIOC_DQEVENT, event_buf)
        event_type = struct.unpack('I', event_buf[0:4])[0]
        
        if event_type == UVC_EVENT_SETUP:
            print("Received UVC setup request")
            handle_setup_event(fd, event_buf)
        elif event_type == UVC_EVENT_DATA:
            print("Received UVC data event")
        elif event_type == UVC_EVENT_STREAMON:
            print("Received stream ON request")
        elif event_type == UVC_EVENT_STREAMOFF:
            print("Received stream OFF request")
    except Exception as e:
        if hasattr(e, 'errno') and e.errno == 11:  # EAGAIN - no events available
            pass
        else:
            print(f"Error handling event: {e}")

def main():
    try:
        device_path = "/dev/video0"
        print(f"Opening {device_path}")
        fd = os.open(device_path, os.O_RDWR | os.O_NONBLOCK)
        
        # Subscribe to events
        event_types = [UVC_EVENT_SETUP, UVC_EVENT_DATA, UVC_EVENT_STREAMON, UVC_EVENT_STREAMOFF]
        for event_type in event_types:
            try:
                subscribe_event(fd, event_type)
                print(f"Successfully subscribed to event 0x{event_type:08x}")
            except Exception as e:
                print(f"Failed to subscribe to event 0x{event_type:08x}: {e}")
                os.close(fd)
                return

        print("\nWaiting for USB setup requests...")
        
        # Create poll object for monitoring the fd
        poll = select.poll()
        poll.register(fd, select.POLLIN | select.POLLPRI)
        
        while True:
            # Wait for events with a timeout
            events = poll.poll(1000)  # 1 second timeout
            for fd, event in events:
                handle_event(fd)
            
            # Small sleep to prevent tight loop
            time.sleep(0.01)

    except KeyboardInterrupt:
        print("\nExiting...")
    finally:
        if 'fd' in locals():
            os.close(fd)
            print("Closed device")

if __name__ == "__main__":
    main()