import paho.mqtt.client as mqtt
from min import *
from uuid import getnode
import base64

# enable or disable debug
debug = True

# read out the mac address to identify the machine
mac = getnode()
h = iter(hex(mac)[2:].replace('L','').zfill(12))
mac_address = ":".join(i+next(h) for i in h)
macstr = mac_address.replace(':', '').decode('hex')
machine_identifier = base64.b64encode(macstr)

#variable decleration
message_id = 0
data = 0
rec_client = 0
error_id = 0xFF
error_data = 0


if debug:
    print("mac address:")
    print(mac_address)
    print(machine_identifier)


error = ([0xFF])
init  = ([0x10])
shoot = ([0x11])
get_position = ([0xF1])

low_level_id    =   "football/machine/status/"
low_level       =   "football/machine/"
top_level       =   str(machine_identifier)

# broker mosquitto
broker                      =  "localhost"

# subscriber topics
topic_sub_init              =  low_level    + top_level + "/to/command/init"
topic_sub_shoot             =  low_level    + top_level + "/to/command/shoot"
topic_sub_coordinate        =  low_level    + top_level + "/to/command/coordinate"
topic_sub_elevation         =  low_level    + top_level + "/to/command/elevation"
topic_sub_azimut            =  low_level    + top_level + "/to/command/azimut"
topic_sub_speed             =  low_level    + top_level + "/to/command/speed"
topic_sub_request_position  =  low_level    + top_level + "/to/command/status/position"

# publisher topics
topic_pub_status_position   =  low_level    + top_level + "/from/status/position"
topic_pub_lookuptable       =  low_level    + top_level + "/from/lookup_table"
topic_pub_ack               =  low_level    + top_level + "/from/acknowledge"
topic_pub_error             =  low_level    + top_level + "/from/error"
topic_pub_id                =  low_level_id + top_level

def array_to_str(message_id, payload):
    i = 0;
    return payload;

#split message from broker to single terms
def str_to_list(client_data): 
    client_data = client_data.replace(";",":")
    data = client_data.split(":")
    for i in data:
        print(i)

    identifier = int(data[1])
    if identifier == 0xF1:      #Status
        rec_data = list([identifier])
    
    elif identifier == 0xF2:    #Acknolage
        rec_data = list([identifier])
    
    elif identifier == 0xF3:    #Lookuptable
        rec_data = list([identifier])
    
    elif identifier == 0xFF:    #Error 
        rec_data = list([identifier])
   
    elif identifier == 0x10:
        rec_data = list([identifier])

    elif identifier == 0x11:    #Shoot
        shoot_time  = int(data[3]) 
        print shoot_time
        shoot_time_high = (shoot_time >> 8) &0xFF
        shoot_time_low = shoot_time & 0xFF
        rec_data    = list([identifier, shoot_time_low, shoot_time_high])
        
    elif identifier == 0x12:    #Coordinate
        x_coordinate = float(data[3]) * 10
        y_coordinate = float(data[5]) * 10
        x_coordinate = int(x_coordinate)
        y_coordinate = int(y_coordinate)
        hang = int(data[7])
        print x_coordinate
        print y_coordinate
        x_coord_high = (x_coordinate >> 8) & 0xFF
        x_coord_low  = x_coordinate & 0xFF
        y_coord_high = (y_coordinate >> 8) & 0xFF
        y_coord_low  = y_coordinate & 0xFF
        rec_data     = list([identifier, x_coord_low, x_coord_high, y_coord_low, y_coord_high, hang]) 

    elif identifier == 0x13:    #Elevation
        elevation      = float(data[3]) * 10
        elevation      = int(elevation)
        print elevation
        elevation_high = (elevation >> 8) & 0xFF
        elevation_low  = elevation & 0xFF
        rec_data       = list([identifier, elevation_low, elevation_high])
    
    elif identifier == 0x14:    #Azimut
        azimut         = float(data[3]) * 10
        azimut         = int(azimut)
        print azimut
        azimut_high    = (azimut >> 8) & 0xFF
        azimut_low     = azimut & 0xFF 
        rec_data = list([identifier, azimut_low, azimut_high])

    elif identifier == 0x15:    #Speed
        speed = int(data[3])
        print speed
        rec_data = list([identifier, speed])

    else:
        rec_data = list([0xFF])

    return rec_data

#    try:
#        client_data = bytearray.fromhex(client_data)
#    except ValueError:
#        return False




# read out the ID and send message from uart to broker
def publish_to_broker(message_ID, payload):
    payload = bytearray(payload)
    if message_ID == 0xF1:                                  #Status position
        message = array_to_str(messageID, payload)
        if message == False:
            message = error
        client.publish(topic_pub_status_position, message)
    elif message_ID == 0xF2:                                #Acknolage
        client.publish(topic_pub_ack)
    elif message_ID == 0xF3:                                #Lookup table 
        message = array_to_str(messageID, payload)
        client.publish(topic_pub_lookup, message) 
    elif message_ID == 0xFF:                                #error
        client.publish(topic_pub_error)
    else:
        client.publish(topic_pub_error)


def uart_receive():
    global rec_client, message_id, data
    msg_ID, payload = get_uart_rec_data()
    if rec_client == 1:
        rec_client = 0
        if msg_ID == message_id:
            if payload == data:
                data = 0
                message_id = 0xF2
                publish_to_broker(message_id, data)
        else:
            data = 0
            message_id = 0xFF
            publish_to_broker(message_id, data)

    else:
        publish_to_broker(msg_ID, payload)
        

def uart_send(send_data):
    global rec_client, message_id, data
    if send_data == error:
       publish_to_broker(error_id, error_data) 
    else:
        rec_client = 1
        message_id = send_data[0]
        data = send_data[1:]
        min_uart_send(message_id,data)
        if debug:
            print("Data TX: %s" % ':'.join('0x{:02x}'.format(i) for i in send_data)) 


def on_connect(client, userdata, flags, rc):
    CModule.InterruptUartReadOn()
    if debug:
        print("Connect with result code: " + str(rc))
#    client.will_set(topic_pub_id, "Offline", qos = 1, retain = True)
    client.subscribe([  (topic_sub_init, 2), 
                        (topic_sub_shoot, 2), 
                        (topic_sub_coordinate, 2), 
                        (topic_sub_elevation, 2), 
                        (topic_sub_azimut, 2), 
                        (topic_sub_speed, 2), 
                        (topic_sub_request_position,2)])


def on_message(client, userdata, msg):
    global message
    CModule.InterruptUartReadOn()

    if debug:
        print(msg.topic + " " + str(msg.qos) + " " + str(msg.payload))
    message = msg.payload

    if msg.topic == topic_sub_init:
        message = init
        if message == False:
            message = error
        uart_send(message)

    elif msg.topic == topic_sub_shoot:
        message = str_to_list(message)
#        message = shoot
        if message == False:
            message = error
        uart_send(message)

    elif msg.topic == topic_sub_coordinate:
        message = str_to_list(message)
        if message == False:
            message = error
        uart_send(message)

    elif msg.topic == topic_sub_elevation:
        message = str_to_list(message)
        if message == False:
            message = error
        uart_send(message)

    elif msg.topic == topic_sub_azimut:
        message = str_to_list(message)
        if message == False:
            message = error
        uart_send(message)

    elif msg.topic == topic_sub_speed:
        message = str_to_list(message)
        if message == False:
            message = error
        uart_send(message)

    elif msg.topic == topic_sub_request_position:
        message = get_position
        uart_send(message)

    else: 
        message = error
        uart_send(message)

def on_publish(client, userdata, mid):
    if debug:
        print("mid: " + str(mid))
    CModule.InterruptUartReadOff()


def on_subscribe(client, userdata, mid, granted_qos):
    if debug:
        print("Subscribed: " + str(mid) + " " + str(granted_qos))
#    client.publish(topic_pub_id, "Online", qos = 1, retain = True)
    CModule.InterruptUartReadOff()


def on_log(client, userdata, level, string):
    if debug:
        print(string)


client = mqtt.Client()
# Assign event callbacks
client.on_message = on_message
client.on_connect = on_connect
client.on_publish = on_publish
client.on_subscribe = on_subscribe
client.publish(topic_pub_id, "Online", qos = 1, retain = True)
client.will_set(topic_pub_id, "Offline", qos = 1, retain = True)

# Connect
client.connect(host = broker, port = 1883, keepalive = 60)
client.loop_start()
init_controller()


def uartStatus():
    while(not uart_stop.is_set()):
        uart_rec_status = get_uart_status()
        if uart_rec_status >= 1:
            print "Uart start: " + str(uart_rec_status)
        if uart_rec_status == 1:
            uart_receive()


uart_stop = threading.Event()
thread = threading.Thread(target = uartStatus)
thread.start()
thread.join()

