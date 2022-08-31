import asyncio
import csv
import json
import os

import gphoto2 as gp
import pandas as pd
import torch
from azure.iot.device import Message
from azure.iot.device.aio import IoTHubDeviceClient
from azure.iot.device.aio import ProvisioningDeviceClient

import createSkybox
import cutSkybox


async def main(location_id):
    print('-' * 30)
    # ––––– Define IOT central Variables saved in the CSV file ––––– #
    env_var_path = os.path.join(os.path.dirname(__file__), 'DeviceEnvVar_EEODetection.csv')
    with open(env_var_path, newline='') as fp:
        csvreader = csv.DictReader(fp)
        for row in csvreader:
            Device = row

    IOTHUB_DEVICE_SECURITY_TYPE = Device['IOTHUB_DEVICE_SECURITY_TYPE']
    IOTHUB_DEVICE_DPS_ID_SCOPE = Device['IOTHUB_DEVICE_DPS_ID_SCOPE']
    IOTHUB_DEVICE_DPS_DEVICE_KEY = Device['IOTHUB_DEVICE_DPS_DEVICE_KEY']
    IOTHUB_DEVICE_DPS_DEVICE_ID = Device['IOTHUB_DEVICE_DPS_DEVICE_ID']
    IOTHUB_DEVICE_DPS_ENDPOINT = Device['IOTHUB_DEVICE_DPS_ENDPOINT']

    # conn_str = Device['AZURE_WEB_STORAGE_CONNECTION_STRING']
    model_id = Device['model_id']

    # ––––– Connecting to IoT Central ––––– #
    switch = IOTHUB_DEVICE_SECURITY_TYPE
    if switch == "DPS":
        provisioning_host = (
            IOTHUB_DEVICE_DPS_ENDPOINT
            if IOTHUB_DEVICE_DPS_ENDPOINT
            else "global.azure-devices-provisioning.net"
        )
        id_scope = IOTHUB_DEVICE_DPS_ID_SCOPE
        registration_id = IOTHUB_DEVICE_DPS_DEVICE_ID
        symmetric_key = IOTHUB_DEVICE_DPS_DEVICE_KEY

        registration_result = await provision_device(
            provisioning_host, id_scope, registration_id, symmetric_key, model_id
        )

        if registration_result.status == "assigned":
            print("Device was assigned")
            print(registration_result.registration_state.assigned_hub)
            print(registration_result.registration_state.device_id)

            device_client = IoTHubDeviceClient.create_from_symmetric_key(
                symmetric_key=symmetric_key,
                hostname=registration_result.registration_state.assigned_hub,
                device_id=registration_result.registration_state.device_id,
                product_info=model_id,
            )
        else:
            raise RuntimeError(
                "Could not provision device. Aborting Plug and Play device connection."
            )

    elif switch == "connectionString":
        conn_str = os.getenv("IOTHUB_DEVICE_CONNECTION_STRING")
        print("Connecting using Connection String " + conn_str)
        device_client = IoTHubDeviceClient.create_from_connection_string(
            conn_str, product_info=model_id
        )
    else:
        raise RuntimeError(
            "At least one choice needs to be made for complete functioning of this sample."
        )

    await device_client.connect()
    # ––––– End of Connecting to IoT Central ––––– #

    image_name = captureImage()
    cubemap_name = createSkybox.main(image_name)
    image_to_be_inferenced = cutSkybox.main(cubemap_name)

    # Model
    model = torch.hub.load('ultralytics/yolov5', 'yolov5x6', pretrained=True)
    model.conf = 0.7
    img = image_to_be_inferenced
    results = model(img)
    results.print()

    # Populate a pandas DataFrame with the results
    res_json = results.pandas().xyxy[0].to_json(orient="records")
    df = pd.read_json(res_json, orient='records')

    obstruction_detected = False

    if 'name' in df.columns:
        print('Object(s) detected. Emergency Exit pathway is obstructed!')
        obstruction_detected = True
    else:
        print('No objects detected. Emergency Exit pathway is clear.')

    # Send telemetry
        # Send the data as telemetries to Azure IoT Central | WIP
        async def send_telemetry():

            WIP_EEODetection_msg = {
                "LocationID": float(location_id),
                "ObstructionDetected": bool(obstruction_detected)
            }

            await send_telemetry_from_nano(device_client, WIP_EEODetection_msg)
            await asyncio.sleep(8)

        await send_telemetry()
        await device_client.shutdown()
        print('Telemetries have been sent to IoT Central')

        print('-' * 30)


def captureImage():
    # Capturing the image via USB
    camera = gp.Camera()
    camera.init()
    print('Capturing image')
    file_path = camera.capture(gp.GP_CAPTURE_IMAGE)
    print('Camera file path: {0}/{1}'.format(file_path.folder, file_path.name))
    target = os.path.join(os.path.dirname(__file__), file_path.name)
    print('Copying image to', target)
    camera_file = camera.file_get(
        file_path.folder, file_path.name, gp.GP_FILE_TYPE_NORMAL)
    camera_file.save(target)
    camera.exit()

    # Return the image name to be used for creating a skybox of the panoramic image
    return str(file_path.name)


#####################################################
# Azure async Functions

async def provision_device(provisioning_host, id_scope, registration_id, symmetric_key, model_id):
    provisioning_device_client = ProvisioningDeviceClient.create_from_symmetric_key(
        provisioning_host=provisioning_host,
        registration_id=registration_id,
        id_scope=id_scope,
        symmetric_key=symmetric_key,
    )
    provisioning_device_client.provisioning_payload = {"modelId": model_id}
    return await provisioning_device_client.register()


async def send_telemetry_from_nano(device_client, telemetry_msg):
    msg = Message(json.dumps(telemetry_msg))
    msg.content_encoding = "utf-8"
    msg.content_type = "application/json"
    print("Sent message")
    await device_client.send_message(msg)

# END TELEMETRY Functions
#####################################################
