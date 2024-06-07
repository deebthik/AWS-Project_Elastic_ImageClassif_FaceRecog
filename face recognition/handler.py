
import urllib.parse
import os
import boto3

from face-recognition import faceRecognition as faceRecFunc


def cleanUp(imagePath, outputFilename):
    os.remove(imagePath)
    if os.path.exists("/tmp/" + outputFilename):
        os.remove("/tmp/" + outputFilename)


def handler(event, context):

  record = event['Records'][0]['s3']
  bucket = record['bucket']['name']
  key = urllib.parse.unquote_plus(record['object']['key'], encoding='utf-8')
  outputFilename = os.path.splitext(key)[0] + ".txt"

  outputBucket = "1229479357-output"
  image_path = "/tmp/{}".format(key)

  s3Client = boto3.client('s3')
  s3Client.download_file(bucket, key, imagePath)
  
  resultName = faceRecFunc(imagePath)

  with open("/tmp/" + outputFilename, 'w+') as f:
    f.write(resultName)
  s3Client.upload_file("/tmp/" + outputFilename, outputBucket, outputFilename)


  cleanUp(image_path, outputFilename)
  
  



