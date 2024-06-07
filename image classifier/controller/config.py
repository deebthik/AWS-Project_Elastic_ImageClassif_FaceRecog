#AWS Credentials
REGION="us-east-1"
ACCESS_KEY="AKIA5FTY6QOVPI6LFUX6"
SECRET_KEY="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"

#AWS SQS
REQ_SQS_QUEUE_URL="https://sqs.us-east-1.amazonaws.com/905418015658/1225344536-req-queue"
RES_SQS_QUEUE_URL="https://sqs.us-east-1.amazonaws.com/905418015658/1225344536-resp-queue"
SQS_MAX_NUMBER_OF_MESSAGES=10
SQS_VISIBILITY_TIMEOUT=0
SQS_WAIT_TIME_SECONDS=10

#AWS S3
INPUT_S3_BUCKET_NAME="1225344536-in-bucket"
OUTPUT_S3_BUCKET_NAME="1225344536-out-bucket"

#AWS EC2
AMI_ID="ami-0ef27cef319ced260"
INSTANCE_TYPE="t2.micro"

#AWS Auto Scaling Group
ASG_NAME = "app-tier-asg"

#codes
RES_NOT_FOUND_CODE = "message not found yet"
SQS_ERROR_CODE = "error in pushing to req SQS"