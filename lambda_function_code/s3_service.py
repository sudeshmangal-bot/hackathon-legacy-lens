import boto3

s3 = boto3.client("s3")
s3_vectors = boto3.client("s3vectors", region_name="us-east-1")


def generate_presigned_url(bucket_name: str, filename: str, content_type: str, project_id: str):
    file_key = f"projects/{project_id}/raw_data/{filename}"
    url = s3.generate_presigned_url(
        "put_object",
        Params={
            "Bucket": bucket_name,
            "Key": file_key,
            "ContentType": content_type
        },
        ExpiresIn=300
    )
    return {"filename": filename, "upload_url": url, "s3_key": file_key}


def create_vector_bucket(bucket_name: str):
    response = s3_vectors.create_vector_bucket(vectorBucketName=bucket_name)
    return response.get("vectorBucketArn")


def create_vector_index(bucket_name: str, index_name: str):
    return s3_vectors.create_index(
        vectorBucketName=bucket_name,
        indexName=index_name,
        dataType='float32',
        dimension=1536,
        distanceMetric='cosine'
    )


def delete_vector_index(bucket_name: str, index_name: str):
    s3_vectors.delete_index(vectorBucketName=bucket_name, indexName=index_name)


def delete_vector_bucket(bucket_name: str):
    s3_vectors.delete_vector_bucket(vectorBucketName=bucket_name)


def list_s3_files(bucket_name: str, prefix: str):
    files = []
    paginator = s3.get_paginator('list_objects_v2')
    for page in paginator.paginate(Bucket=bucket_name, Prefix=prefix):
        for obj in page.get('Contents', []):
            files.append({'key': obj['Key'], 'etag': obj['ETag']})
    return sorted(files, key=lambda f: f['key'])
