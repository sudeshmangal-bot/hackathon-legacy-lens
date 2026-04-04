import os
import logging

from services.bedrock_service import (
    create_agent, prepare_agent, delete_agent,
    associate_agent_knowledge_base, disassociate_agent_knowledge_base
)

logger = logging.getLogger(__name__)

_instructions_path = os.path.join(os.path.dirname(__file__), 'agent_instructions.md')
with open(_instructions_path, 'r') as f:
    AGENT_INSTRUCTION = f.read()

def create_agent_draft(agent_name: str, role_arn: str):
    agent_id = None
    try:
        agent = create_agent(agent_name, role_arn, AGENT_INSTRUCTION)['agent']
        agent_id = agent['agentId']
        return {
            'agentId': agent_id,
            'agentArn': agent['agentArn'],
            'agentName': agent['agentName'],
            'agentStatus': agent['agentStatus']
        }
    except Exception as e:
        logger.error(f"Agent creation failed: {e}")
        if agent_id:
            try: delete_agent(agent_id)
            except Exception as ex: logger.warning(f"Cleanup delete_agent failed: {ex}")
        raise


def associate_kb_to_agent(agent_id: str, kb_id: str, kb_description: str):
    try:
        associate_agent_knowledge_base(agent_id, 'DRAFT', kb_id, kb_description)
        prepare_agent(agent_id)
        return {'agentId': agent_id, 'knowledgeBaseId': kb_id}
    except Exception as e:
        logger.error(f"KB association failed: {e}")
        try: disassociate_agent_knowledge_base(agent_id, 'DRAFT', kb_id)
        except Exception as ex: logger.warning(f"Cleanup disassociate KB failed: {ex}")
        raise
