

import os
import cv2
import json
from PIL import Image, ImageDraw, ImageFont
from facenet_pytorch import MTCNN, InceptionResnetV1
from shutil import rmtree
import numpy as np
import torch
import boto3


mtcnn = MTCNN(image_size=240, margin=0, min_face_size=20)
resnet = InceptionResnetV1(pretrained='vggface2').eval()

def faceRecognition(key_path):

    img = cv2.imread(key_path, cv2.IMREAD_COLOR)
    boxes, _ = mtcnn.detect(img)

    s3Client = boto3.client('s3')
    dataBucketName = "1229479357-model" 
    dataFilename = "data.pt"
    downloadPath = "/tmp/data.pt"

    
    s3Client.download_file(dataBucketName, dataFilename, downloadPath)

    savedData = torch.load(downloadPath)
    
    key = os.path.splitext(os.path.basename(key_path))[0].split(".")[0]
    img = Image.fromarray(cv2.cvtColor(img, cv2.COLOR_BGR2RGB))
    face, prob = mtcnn(img, return_prob=True, save_path=None)
    savedData = torch.load('/tmp/data.pt') 
    if face != None:
        emb = resnet(face.unsqueeze(0)).detach() 
        embedding_list = savedData[0] 
        name_list = savedData[1] 
        dist_list = []  
        for idx, emb_db in enumerate(embedding_list):
            dist = torch.dist(emb, emb_db).item()
            dist_list.append(dist)
        idx_min = dist_list.index(min(dist_list))

        with open("/tmp/" + key + ".txt", 'w+') as f:
            f.write(name_list[idx_min])
        return name_list[idx_min]
    else:
        print(f"No face is detected")
    return



