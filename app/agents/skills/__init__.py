"""
Agent Skills - Specialized agents for different domains.
"""

from app.agents.skills.code_agent import CodeAgent
from app.agents.skills.communication_agent import CommunicationAgent
from app.agents.skills.data_agent import DataAgent
from app.agents.skills.deploy_agent import DeployAgent
from app.agents.skills.file_agent import FileAgent
from app.agents.skills.monitor_agent import MonitorAgent
from app.agents.skills.research_agent import ResearchAgent
from app.agents.skills.skill_creator_agent import SkillCreatorAgent
from app.agents.skills.scheduler_agent import SchedulerAgent
from app.agents.skills.shell_agent import ShellAgent
from app.agents.skills.trading_agent import TradingAgent
from app.agents.skills.web_agent import WebAgent
from app.agents.skills.brave_search_agent import BraveSearchAgent
from app.agents.skills.image_agent import ImageAgent
from app.agents.skills.video_agent import VideoAgent
from app.agents.skills.legal_agent import LegalAgent
from app.agents.skills.apex_architect_agent import ApexArchitectAgent
from app.agents.skills.scout_agent import ScoutAgent
from app.agents.skills.analyst_agent import AnalystAgent
from app.agents.skills.outreach_agent import OutreachAgent
from app.agents.skills.provisioning_agent import ProvisioningAgent
from app.agents.skills.market_pulse_agent import MarketPulseAgent
from app.agents.skills.profitability_analyst_agent import ProfitabilityAnalystAgent
from app.agents.skills.neighborhood_growth_agent import NeighborhoodGrowthAgent
from app.agents.skills.deal_flow_agent import DealFlowAgent
from app.agents.skills.chronos_agent import ChronosAgent
from app.agents.skills.archivist_agent import ArchivistAgent
from app.agents.skills.sentinel_agent import SentinelAgent
from app.agents.skills.synthesis_agent import SynthesisAgent
from app.agents.skills.content_extractor_agent import ContentExtractorAgent
from app.agents.skills.ad_pipeline_agent import AdPipelineAgent
from app.agents.skills.new_agent import NewAgent

__all__ = [
    "ShellAgent",
    "WebAgent",
    "CodeAgent",
    "FileAgent",
    "TradingAgent",
    "DeployAgent",
    "ResearchAgent",
    "CommunicationAgent",
    "SchedulerAgent",
    "DataAgent",
    "MonitorAgent",
    "SkillCreatorAgent",
    "BraveSearchAgent",
    "ImageAgent",
    "VideoAgent",
    "LegalAgent",
    "ApexArchitectAgent",
    "ScoutAgent",
    "AnalystAgent",
    "OutreachAgent",
    "ProvisioningAgent",
    "MarketPulseAgent",
    "ProfitabilityAnalystAgent",
    "NeighborhoodGrowthAgent",
    "DealFlowAgent",
    "ChronosAgent",
    "ArchivistAgent",
    "SentinelAgent",
    "SynthesisAgent",
    "ContentExtractorAgent",
    "AdPipelineAgent",
    "NewAgent",
]
