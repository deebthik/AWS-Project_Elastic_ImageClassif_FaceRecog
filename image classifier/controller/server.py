from flask import Flask, request
import boto3
import config as config
from flask_apscheduler import APScheduler
from botocore.exceptions import ClientError
import uuid
import json
import time
import base64

app = Flask(__name__)

# initialize scheduler
scheduler = APScheduler()
scheduler.api_enabled = True
scheduler.init_app(app)
scheduler.start()

# List to track instance IDs
instance_ids = []

session = boto3.Session(
    region_name="us-east-1",
    aws_access_key_id=config.ACCESS_KEY,
    aws_secret_access_key=config.SECRET_KEY
)

class EC2Wrapper:
    def __init__(self, ec2):
        self.ec2 = ec2

    def create_instance(self, ami_id, instance_type):
        try:
            user_data_script = """#!/bin/bash
sudo apt-get update
sudo apt-get install awscli -y
sudo pip3 install boto3
export PATH=$PATH:/usr/local/bin/aws
INSTANCE_ID=$(curl -s http://169.254.169.254/latest/meta-data/instance-id)
NEW_INSTANCE_NAME="app-tier-instance-$INSTANCE_ID"
aws ec2 create-tags --resources $INSTANCE_ID --tags "Key=Name,Value=$NEW_INSTANCE_NAME" --region us-east-1
sudo -u ubuntu python3 /home/ubuntu/project1/app/app.py | tee /home/ubuntu/app-tier/logfile.log
"""
            user_data_b64 = base64.b64encode(user_data_script.encode()).decode()
            response = self.ec2.run_instances(
                ImageId=ami_id,
                InstanceType=instance_type,
                MinCount=1,
                MaxCount=1,
                UserData=user_data_b64
            )
            instance_id = response['Instances'][0]['InstanceId']
            instance_ids.append(instance_id)
            print(f"Instance {instance_id} created")
        except ClientError as e:
            print(f"Error creating instance: {e}")

    def terminate_instance(self, instance_id):
        try:
            self.ec2.terminate_instances(InstanceIds=[instance_id])
            instance_ids.remove(instance_id)
            print(f"Instance {instance_id} terminated")
        except ClientError as e:
            print(f"Error terminating instance {instance_id}: {e}")


class SQSWrapper:
    def __init__(self, sqs_client):
        self.sqs_client = sqs_client

    def get_queue_attributes(self, queueUrl):
        try:
            stats = self.sqs_client.get_queue_attributes(
                QueueUrl=queueUrl,
                AttributeNames=["ApproximateNumberOfMessages"]
            )
        except ClientError as error:
            print(error)
        else:
            return stats

    def process_messages(self):
        try:
            response = self.sqs_client.receive_message(
                QueueUrl=config.RES_SQS_QUEUE_URL,
                MaxNumberOfMessages=config.SQS_MAX_NUMBER_OF_MESSAGES,
                VisibilityTimeout=config.SQS_VISIBILITY_TIMEOUT,
                WaitTimeSeconds=config.SQS_WAIT_TIME_SECONDS
            )

            if "Messages" not in response:
                print("No message received")
                return False
            
            messages = response["Messages"]
            for message in messages:
                message_body = json.loads(message["Body"])

                receipt_handle = message["ReceiptHandle"]
                s3.put_item(message_body)
                self.sqs_client.delete_message(
                    QueueUrl=config.RES_SQS_QUEUE_URL,
                    ReceiptHandle=receipt_handle
                )

            return True

        except ClientError as error:
            print(f"Error while consuming prediction output from sqs {error}")

    def push_to_sqs(self, image_url, request_id):

        try:
            message_json = {
                "image_url": image_url,
                "request_id": request_id
            }
            message_json = json.dumps(message_json)
            response = self.sqs_client.send_message(
                QueueUrl=config.REQ_SQS_QUEUE_URL,
                MessageBody=message_json,
            )
            message_id = response.get('MessageId')
            print(
                f"image url pushed to request sqs and the message id is {message_id}")
            return 200

        except ClientError as error:
            return error

class S3Wrapper:
    def __init__(self, s3_resource):
        self.s3_resource = s3_resource.meta.client

    def upload_to_s3(self, file, bucket, key, content_type):
        upload_file_response = self.s3_resource.put_object(
            Body=file, Bucket=bucket, Key=key, ContentType=content_type)
        status_code = upload_file_response['ResponseMetadata']['HTTPStatusCode']
        print(f"Response - {upload_file_response}")
        return status_code

    def query_db(self, bucket, key):
        try:
            query_response = self.s3_resource.get_object(Bucket=bucket, Key=key)
            return query_response
        except ClientError: 
            return config.RES_NOT_FOUND_CODE
    def write_db(self, bucket, key, body):
        write_response = self.s3_resource.put_object(
            Body=body, Bucket=bucket, Key=key)
        print(f"DB write success! {write_response}")

ec2 = EC2Wrapper(session.client('ec2'))
sqs = SQSWrapper(session.client('sqs'))
s3 = S3Wrapper(session.resource('s3'))

ami_id = config.AMI_ID
instance_type = config.INSTANCE_TYPE

user_data_script = """
#!/bin/bash
sudo apt-get update
sudo apt-get install awscli -y
sudo pip3 install boto3
export PATH=$PATH:/usr/local/bin/aws
INSTANCE_ID=$(curl -s http://169.254.169.254/latest/meta-data/instance-id)
NEW_INSTANCE_NAME="app-tier-instance-$INSTANCE_ID"
aws ec2 create-tags --resources $INSTANCE_ID --tags "Key=Name,Value=$NEW_INSTANCE_NAME" --region us-east-1
sudo -u ubuntu python3 /home/ubuntu/projec1/app/app.py | tee /home/ubuntu/app-tier/logfile.log
"""

@scheduler.task('interval', id='manage_instances', seconds=10, misfire_grace_time=900)
def manage_instances():
    queue_length = sqs.get_queue_attributes(config.REQ_SQS_QUEUE_URL)
    queuel = queue_length["Attributes"]["ApproximateNumberOfMessages"]
    queuel = int(queuel)

    if queuel == 0:
        # Terminate all instances
        for instance_id in instance_ids:
            ec2.terminate_instance(instance_id)
    elif queue_length > 0 and len(instance_ids) < 20:
        # Create instances up to a maximum of 20
        instances_to_create = min(20 - len(instance_ids), queue_length)
        for _ in range(instances_to_create):
            ec2.create_instance(config.AMI_ID, config.INSTANCE_TYPE)


@scheduler.task('interval', id='query_response_queue', seconds=20, misfire_grace_time=60)
def query_response_queue():
    while(sqs.process_messages()):
        print("Processing...")

@app.route("/", methods=["POST"])
def get_image():
    request_type = request.mimetype
    file = request.files['inputFile']
    file_name = file.filename

    request_id = str(uuid.uuid1())
    response = ""
    print(f"The file name to upload is {file_name}")
    print(f"Path is {file}")
    bucket_name = config.INPUT_S3_BUCKET_NAME
    url = f"https://{config.INPUT_S3_BUCKET_NAME}.s3.amazonaws.com/{file_name}"
    s3_upload_status = s3.upload_to_s3(
        file, bucket_name, file_name, request_type)
    if s3_upload_status == 200:
        print(f"File successfully uploaded to s3 and url is {url}")
    else:
        print("File upload failed")
    sqs_response = sqs.push_to_sqs(url, request_id)
    if sqs_response == 200:
        print(f"Message successfully sent to req SQS")
    else:
        print(sqs_response)
    while (True):
        result = s3.retrieve_item(request_id)
        if result != config.RES_NOT_FOUND_CODE:
            return result["output"]["S"]
        time.sleep(20)


if __name__ == '__main__':
    port = 8000
    app.run(port=port, host='0.0.0.0', threaded=True)