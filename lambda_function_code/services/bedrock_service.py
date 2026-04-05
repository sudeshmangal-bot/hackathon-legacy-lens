import boto3

bedrock_agent = boto3.client('bedrock-agent', region_name='us-east-1')
bedrock_agent_runtime = boto3.client('bedrock-agent-runtime', region_name='us-east-1')


def create_knowledge_base(name: str, role_arn: str, bucket_arn: str, index_name: str):
    return bedrock_agent.create_knowledge_base(
        name=name,
        description=f'Knowledge base for project {name}',
        roleArn=role_arn,
        knowledgeBaseConfiguration={
            'type': 'VECTOR',
            'vectorKnowledgeBaseConfiguration': {
                'embeddingModelArn': 'arn:aws:bedrock:us-east-1::foundation-model/amazon.titan-embed-text-v1'
            }
        },
        storageConfiguration={
            'type': 'S3_VECTORS',
            's3VectorsConfiguration': {
                'vectorBucketArn': bucket_arn,
                'indexName': index_name
            }
        }
    )

def create_data_source(knowledge_base_id: str, name: str, bucket_arn: str, prefix: str = None):
    s3_config = {'bucketArn': bucket_arn}
    if prefix:
        s3_config['inclusionPrefixes'] = [prefix]
    return bedrock_agent.create_data_source(
        knowledgeBaseId=knowledge_base_id,
        name=name,
        dataSourceConfiguration={
            'type': 'S3',
            's3Configuration': s3_config
        },

    )

def start_ingestion_job(knowledge_base_id: str, data_source_id: str):
    return bedrock_agent.start_ingestion_job(
        knowledgeBaseId=knowledge_base_id,
        dataSourceId=data_source_id
    )

def get_ingestion_job_status(knowledge_base_id: str, data_source_id: str, ingestion_job_id: str):
    return bedrock_agent.get_ingestion_job(
        knowledgeBaseId=knowledge_base_id,
        dataSourceId=data_source_id,
        ingestionJobId=ingestion_job_id
    )['ingestionJob']['status']

def get_knowledge_base_status(knowledge_base_id: str):
    return bedrock_agent.get_knowledge_base(knowledgeBaseId=knowledge_base_id)['knowledgeBase']['status']

def get_data_source_status(knowledge_base_id: str, data_source_id: str):
    return bedrock_agent.get_data_source(
        knowledgeBaseId=knowledge_base_id, dataSourceId=data_source_id
    )['dataSource']['status']

def delete_knowledge_base(knowledge_base_id: str):
    bedrock_agent.delete_knowledge_base(knowledgeBaseId=knowledge_base_id)

def create_agent(name: str, role_arn: str, instruction: str):
    return bedrock_agent.create_agent(
        agentName=name,
        agentResourceRoleArn=role_arn,
        foundationModel='amazon.nova-pro-v1:0',
        instruction=instruction
    )

def associate_agent_knowledge_base(agent_id: str, agent_version: str, kb_id: str, description: str):
    return bedrock_agent.associate_agent_knowledge_base(
        agentId=agent_id, agentVersion=agent_version,
        knowledgeBaseId=kb_id, description=description
    )

def prepare_agent(agent_id: str):
    return bedrock_agent.prepare_agent(agentId=agent_id)

def delete_agent(agent_id: str):
    bedrock_agent.delete_agent(agentId=agent_id, skipResourceInUseCheck=True)

def disassociate_agent_knowledge_base(agent_id: str, agent_version: str, kb_id: str):
    bedrock_agent.disassociate_agent_knowledge_base(
        agentId=agent_id, agentVersion=agent_version, knowledgeBaseId=kb_id
    )


def invoke_agent(agent_id: str, agent_alias_id: str, session_id: str, message: str):
    response = bedrock_agent_runtime.invoke_agent(
        agentId=agent_id,
        agentAliasId=agent_alias_id,
        sessionId=session_id,
        inputText=message
    )
    result = ""
    for event in response['completion']:
        if 'chunk' in event:
            result += event['chunk']['bytes'].decode('utf-8')
    return result
