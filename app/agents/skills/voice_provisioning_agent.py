"""
Voice Provisioning Agent — Cipher's 36th Agent
================================================
Automates ElevenLabs voice sourcing: searches the voice library,
generates voices via the Voice Design API, saves them, auditions
with TTS, and writes voice_ids back into the codebase.

This is what Zig could do — now Cipher does it better.

Operations:
    - provision_all: Generate + save + write all empty education voices
    - provision_one: Generate a single voice by name
    - search_library: Search ElevenLabs shared voice library
    - audition: Generate TTS sample for a saved voice
    - status: Check which voices have IDs and which are empty
    - list_voices: List all voices in your ElevenLabs account
"""

import asyncio
import base64
import json
import os
import re
import time
from datetime import datetime
from pathlib import Path
from typing import Optional

import httpx

from app.agents.base import BaseAgent
from app.agents.models import AgentCapability, AgentResult, AgentTask
from app.core.config import settings
from app.core.logging import logger

ELEVENLABS_BASE = "https://api.elevenlabs.io/v1"
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent


# ============================================================================
# Voice specs — pulled from voice_personalities.py
# ============================================================================

EDUCATION_VOICE_SPECS = {
    "Nonna Maria": {
        "subject": "Italian Language",
        "design_prompt": (
            "Older Italian female, warm and nurturing, slight Italian accent, "
            "the voice of a grandmother who insists you eat more, patient but "
            "animated when passionate about food or family"
        ),
        "sample_text": (
            "Ciao, tesoro! Welcome to Nonna's kitchen. Today we learn Italian "
            "the way it should be learned — with food. Repeat after me: "
            "Che buono! That means how delicious!"
        ),
        "model": "eleven_multilingual_v2",
    },
    "Teacher Lin": {
        "subject": "Mandarin Chinese",
        "design_prompt": (
            "Young Chinese female, clear and patient, precise tonal pronunciation, "
            "calm and encouraging, modern professional, switches naturally between "
            "Mandarin and English"
        ),
        "sample_text": (
            "Ni hao! Let's start with the four tones. Listen carefully — the tone "
            "changes everything. Ma with a flat tone means mother."
        ),
        "model": "eleven_multilingual_v2",
    },
    "The Sage": {
        "subject": "Philosophy",
        "design_prompt": (
            "Mature male, deep contemplative voice, measured pacing, British-influenced "
            "accent, warm but intellectually rigorous, occasional gentle humor, "
            "late-night conversation energy"
        ),
        "sample_text": (
            "Consider this. The Stoics believed the obstacle IS the way. Marcus "
            "Aurelius wrote that in a war tent, ruling an empire. What if your "
            "biggest challenge right now isn't blocking your path — but IS your path?"
        ),
        "model": "eleven_turbo_v2",
    },
    "Blues": {
        "subject": "Music / Harmonica",
        "design_prompt": (
            "Older male, warm gravelly voice, relaxed southern American inflection, "
            "storytelling cadence, blues musician energy, porch wisdom"
        ),
        "sample_text": (
            "Now listen. The harmonica ain't about the notes you play — it's about "
            "the ones you don't. That space between? That's where the blues lives."
        ),
        "model": "eleven_turbo_v2",
    },
    "Dr. Nova": {
        "subject": "Science / Physics",
        "design_prompt": (
            "Middle-aged, gender-neutral, enthusiastic but precise, wonder in the "
            "voice, someone who finds the universe genuinely miraculous, clear for "
            "technical concepts"
        ),
        "sample_text": (
            "Imagine you're riding a beam of light. That's what Einstein did at "
            "sixteen — just imagined it. And that single thought experiment rewrote "
            "our understanding of space, time, and reality."
        ),
        "model": "eleven_turbo_v2",
    },
    "Professor Clarity": {
        "subject": "Mathematics",
        "design_prompt": (
            "Young professional female, extremely clear articulation, patient, "
            "encouraging when students struggle, calm confidence"
        ),
        "sample_text": (
            "Step by step. Don't worry about the whole equation — just focus on "
            "what's inside the parentheses first. Once we solve that piece, the "
            "rest unfolds naturally."
        ),
        "model": "eleven_turbo_v2",
    },
    "The Chronicler": {
        "subject": "History",
        "design_prompt": (
            "Mature male, rich storytelling voice, dramatic but not theatrical, "
            "documentary narrator crossed with fireside storyteller"
        ),
        "sample_text": (
            "It's 49 BC. Caesar stands at the Rubicon with his legion. Cross it, "
            "and there's no going back — it means war with Rome itself."
        ),
        "model": "eleven_turbo_v2",
    },
    "The Muse": {
        "subject": "Writing / Creative",
        "design_prompt": (
            "Young female, lyrical, expressive, varies pace, whispers for emphasis, "
            "energetic for exciting passages"
        ),
        "sample_text": (
            "Close your eyes. Think of the last time you felt something so strongly "
            "you couldn't speak. THAT is what we're putting on paper today."
        ),
        "model": "eleven_turbo_v2",
    },
    "The Founder": {
        "subject": "Business / Entrepreneurship",
        "design_prompt": (
            "Male, confident, direct, startup energy, speaks from experience, "
            "occasional intensity"
        ),
        "sample_text": (
            "Here's what they don't teach you in business school. Your first idea "
            "is almost never the right one. But it's the START. Go talk to ten "
            "customers this week."
        ),
        "model": "eleven_turbo_v2",
    },
    "Profesora Sofia": {
        "subject": "Spanish Language",
        "design_prompt": (
            "Young Spanish female, warm, musical voice, natural rhythm between "
            "Spanish and English, encouraging, expressive"
        ),
        "sample_text": (
            "Hola! Spanish is the language of passion, of Neruda's poetry, of "
            "salsa, of families around a table. Today we start with the most "
            "important word: corazon. Heart."
        ),
        "model": "eleven_multilingual_v2",
    },
}


class VoiceProvisioningAgent(BaseAgent):
    """
    Automates voice provisioning via ElevenLabs API.
    Searches, generates, saves, auditions, and writes voice_ids.
    """

    def __init__(self):
        super().__init__(
            name="voice_provisioning_agent",
            description="Provision education voices via ElevenLabs Voice Design API",
            version="1.0.0",
            capabilities=[
                AgentCapability(name="provision_all", description="Generate + save + write all empty education voices", category="voice", requires_approval=False),
                AgentCapability(name="provision_one", description="Provision a single voice by name", category="voice", requires_approval=False),
                AgentCapability(name="search_library", description="Search ElevenLabs shared voice library", category="voice", requires_approval=False),
                AgentCapability(name="audition", description="Generate TTS sample for a saved voice", category="voice", requires_approval=False),
                AgentCapability(name="status", description="Check which voices have IDs", category="voice", requires_approval=False),
                AgentCapability(name="list_voices", description="List all voices in your ElevenLabs account", category="voice", requires_approval=False),
            ],
        )
        self.api_key = settings.elevenlabs_api_key or os.environ.get("ELEVENLABS_API_KEY", "")
        self.output_dir = Path("/tmp/cipher_data/voice_provisioning")
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def _headers(self) -> dict:
        return {
            "xi-api-key": self.api_key,
            "Content-Type": "application/json",
        }

    # ── Core API methods ──────────────────────────────────────────────

    async def _design_voice(self, client: httpx.AsyncClient, name: str, spec: dict) -> list[dict]:
        """Call Voice Design API to generate preview candidates."""
        logger.info(f"[voice_prov] Designing voice: {name}")

        resp = await client.post(
            f"{ELEVENLABS_BASE}/text-to-voice/design",
            headers=self._headers(),
            json={
                "voice_description": spec["design_prompt"],
                "text": spec["sample_text"][:1000],
            },
            timeout=60.0,
        )
        resp.raise_for_status()
        data = resp.json()

        previews = data.get("previews", [])
        if not previews and "generated_voice_id" in data:
            previews = [data]

        logger.info(f"[voice_prov] {name}: {len(previews)} previews generated")
        return previews

    async def _save_voice(self, client: httpx.AsyncClient, name: str, generated_voice_id: str) -> str:
        """Save a generated voice preview to ElevenLabs account. Returns permanent voice_id."""
        logger.info(f"[voice_prov] Saving voice: {name}")

        resp = await client.post(
            f"{ELEVENLABS_BASE}/text-to-voice/create",
            headers=self._headers(),
            json={
                "voice_name": f"Cipher - {name}",
                "voice_description": f"Cipher education voice: {name}",
                "generated_voice_id": generated_voice_id,
            },
            timeout=30.0,
        )
        resp.raise_for_status()
        data = resp.json()
        voice_id = data.get("voice_id", "")
        logger.info(f"[voice_prov] Saved {name}: voice_id={voice_id}")
        return voice_id

    async def _tts_sample(self, client: httpx.AsyncClient, name: str, voice_id: str, spec: dict) -> Optional[str]:
        """Generate a TTS audio sample and save as MP3."""
        resp = await client.post(
            f"{ELEVENLABS_BASE}/text-to-speech/{voice_id}",
            headers={**self._headers(), "Accept": "audio/mpeg"},
            json={
                "text": spec["sample_text"],
                "model_id": spec.get("model", "eleven_turbo_v2"),
                "voice_settings": {
                    "stability": 0.5,
                    "similarity_boost": 0.75,
                    "style": 0.3,
                },
            },
            timeout=60.0,
        )

        if resp.status_code != 200:
            logger.warning(f"[voice_prov] TTS failed for {name}: {resp.status_code}")
            return None

        safe_name = name.lower().replace(" ", "_").replace(".", "")
        filepath = self.output_dir / f"{safe_name}.mp3"
        filepath.write_bytes(resp.content)
        logger.info(f"[voice_prov] Sample saved: {filepath} ({len(resp.content)} bytes)")
        return str(filepath)

    async def _search_library(self, client: httpx.AsyncClient, query: str, page_size: int = 10) -> list[dict]:
        """Search ElevenLabs shared voice library."""
        resp = await client.get(
            f"{ELEVENLABS_BASE}/shared-voices",
            headers=self._headers(),
            params={
                "search": query,
                "page_size": page_size,
                "sort": "usage_character_count_7d",  # Popular voices first
            },
            timeout=30.0,
        )
        resp.raise_for_status()
        data = resp.json()
        voices = data.get("voices", [])
        return [{
            "voice_id": v.get("voice_id", ""),
            "name": v.get("name", ""),
            "description": v.get("description", ""),
            "preview_url": v.get("preview_url", ""),
            "labels": v.get("labels", {}),
            "category": v.get("category", ""),
        } for v in voices]

    async def _list_account_voices(self, client: httpx.AsyncClient) -> list[dict]:
        """List all voices in the ElevenLabs account."""
        resp = await client.get(
            f"{ELEVENLABS_BASE}/voices",
            headers=self._headers(),
            timeout=30.0,
        )
        resp.raise_for_status()
        data = resp.json()
        return [{
            "voice_id": v.get("voice_id", ""),
            "name": v.get("name", ""),
            "category": v.get("category", ""),
            "labels": v.get("labels", {}),
        } for v in data.get("voices", [])]

    # ── Write voice_ids back to code ──────────────────────────────────

    def _write_voice_id(self, name: str, voice_id: str) -> bool:
        """Write a voice_id into voice_personalities.py."""
        vp_path = PROJECT_ROOT / "app" / "services" / "voice_personalities.py"
        content = vp_path.read_text()

        idx = content.find(f'voice_name="{name}"')
        if idx < 0:
            logger.warning(f"[voice_prov] voice_name='{name}' not found in voice_personalities.py")
            return False

        # Find voice_id="" near the name
        vid_pattern = 'voice_id=""'
        vid_idx = content.find(vid_pattern, idx)
        if vid_idx > 0 and vid_idx - idx < 300:
            content = content[:vid_idx] + f'voice_id="{voice_id}"' + content[vid_idx + len(vid_pattern):]
            vp_path.write_text(content)
            logger.info(f"[voice_prov] Written: {name} → {voice_id}")
            return True

        # Already has a voice_id — replace it
        old_match = re.search(r'voice_id="([^"]*)"', content[idx:idx + 300])
        if old_match:
            old_full = f'voice_id="{old_match.group(1)}"'
            new_full = f'voice_id="{voice_id}"'
            replace_idx = content.find(old_full, idx)
            if replace_idx > 0:
                content = content[:replace_idx] + new_full + content[replace_idx + len(old_full):]
                vp_path.write_text(content)
                logger.info(f"[voice_prov] Replaced: {name} → {voice_id}")
                return True

        return False

    def _get_current_status(self) -> dict:
        """Check which education voices have IDs and which are empty."""
        vp_path = PROJECT_ROOT / "app" / "services" / "voice_personalities.py"
        content = vp_path.read_text()

        status = {}
        for name, spec in EDUCATION_VOICE_SPECS.items():
            idx = content.find(f'voice_name="{name}"')
            if idx < 0:
                status[name] = {"status": "NOT_FOUND", "voice_id": "", "subject": spec["subject"]}
                continue

            vid_match = re.search(r'voice_id="([^"]*)"', content[idx:idx + 300])
            if vid_match:
                vid = vid_match.group(1)
                status[name] = {
                    "status": "READY" if vid else "EMPTY",
                    "voice_id": vid,
                    "subject": spec["subject"],
                }
            else:
                status[name] = {"status": "PARSE_ERROR", "voice_id": "", "subject": spec["subject"]}

        return status

    # ── Agent execute ─────────────────────────────────────────────────

    async def execute(self, task: AgentTask) -> AgentResult:
        """Execute voice provisioning operation."""
        operation = task.params.get("operation", "status")

        if not self.api_key:
            return AgentResult(
                agent_name=self.name,
                task_id=task.task_id,
                success=False,
                error="ELEVENLABS_API_KEY not configured",
            )

        try:
            async with httpx.AsyncClient(timeout=120.0) as client:
                if operation == "status":
                    return await self._op_status(task)
                elif operation == "provision_all":
                    return await self._op_provision_all(task, client)
                elif operation == "provision_one":
                    return await self._op_provision_one(task, client)
                elif operation == "search_library":
                    return await self._op_search_library(task, client)
                elif operation == "audition":
                    return await self._op_audition(task, client)
                elif operation == "list_voices":
                    return await self._op_list_voices(task, client)
                else:
                    return AgentResult(
                        agent_name=self.name,
                        task_id=task.task_id,
                        success=False,
                        error=f"Unknown operation: {operation}",
                    )
        except httpx.HTTPStatusError as e:
            error_detail = ""
            try:
                error_detail = e.response.json()
            except Exception:
                error_detail = e.response.text[:300]
            return AgentResult(
                agent_name=self.name,
                task_id=task.task_id,
                success=False,
                error=f"ElevenLabs API error {e.response.status_code}: {error_detail}",
            )
        except Exception as e:
            return AgentResult(
                agent_name=self.name,
                task_id=task.task_id,
                success=False,
                error=str(e),
            )

    async def _op_status(self, task: AgentTask) -> AgentResult:
        status = self._get_current_status()
        ready = sum(1 for s in status.values() if s["status"] == "READY")
        empty = sum(1 for s in status.values() if s["status"] == "EMPTY")

        return AgentResult(
            agent_name=self.name,
            task_id=task.task_id,
            success=True,
            output={
                "total": len(status),
                "ready": ready,
                "empty": empty,
                "voices": status,
            },
        )

    async def _op_provision_all(self, task: AgentTask, client: httpx.AsyncClient) -> AgentResult:
        """Design + save + write all empty education voices."""
        status = self._get_current_status()
        empty_voices = {name: EDUCATION_VOICE_SPECS[name] for name, s in status.items() if s["status"] == "EMPTY"}

        if not empty_voices:
            return AgentResult(
                agent_name=self.name,
                task_id=task.task_id,
                success=True,
                output={"message": "All education voices already have IDs", "provisioned": 0},
            )

        results = {}
        errors = []

        for name, spec in empty_voices.items():
            try:
                # Step 1: Design
                previews = await self._design_voice(client, name, spec)
                if not previews:
                    errors.append(f"{name}: no previews returned")
                    continue

                gen_id = previews[0].get("generated_voice_id", "")
                if not gen_id:
                    errors.append(f"{name}: no generated_voice_id")
                    continue

                await asyncio.sleep(1)  # Rate limit

                # Step 2: Save to account
                voice_id = await self._save_voice(client, name, gen_id)
                if not voice_id:
                    errors.append(f"{name}: save returned no voice_id")
                    continue

                await asyncio.sleep(1)

                # Step 3: Generate TTS sample
                sample_path = await self._tts_sample(client, name, voice_id, spec)

                await asyncio.sleep(1)

                # Step 4: Write to code
                written = self._write_voice_id(name, voice_id)

                results[name] = {
                    "voice_id": voice_id,
                    "generated_voice_id": gen_id,
                    "sample_path": sample_path,
                    "written_to_code": written,
                    "subject": spec["subject"],
                }

            except Exception as e:
                errors.append(f"{name}: {str(e)}")
                logger.error(f"[voice_prov] Failed for {name}: {e}")

        # Save results JSON
        results_path = self.output_dir / f"provisioned_{int(time.time())}.json"
        with open(results_path, "w") as f:
            json.dump({"results": results, "errors": errors}, f, indent=2)

        return AgentResult(
            agent_name=self.name,
            task_id=task.task_id,
            success=len(results) > 0,
            output={
                "provisioned": len(results),
                "failed": len(errors),
                "results": results,
                "errors": errors,
                "results_file": str(results_path),
            },
        )

    async def _op_provision_one(self, task: AgentTask, client: httpx.AsyncClient) -> AgentResult:
        """Provision a single voice by name."""
        voice_name = task.params.get("voice_name", "")
        if not voice_name:
            # Try to extract from instruction
            for name in EDUCATION_VOICE_SPECS:
                if name.lower() in task.instruction.lower():
                    voice_name = name
                    break

        if voice_name not in EDUCATION_VOICE_SPECS:
            return AgentResult(
                agent_name=self.name,
                task_id=task.task_id,
                success=False,
                error=f"Unknown voice: {voice_name}. Available: {list(EDUCATION_VOICE_SPECS.keys())}",
            )

        spec = EDUCATION_VOICE_SPECS[voice_name]

        # Design
        previews = await self._design_voice(client, voice_name, spec)
        if not previews:
            return AgentResult(agent_name=self.name, task_id=task.task_id, success=False, error="No previews generated")

        gen_id = previews[0].get("generated_voice_id", "")
        await asyncio.sleep(1)

        # Save
        voice_id = await self._save_voice(client, voice_name, gen_id)
        if not voice_id:
            return AgentResult(agent_name=self.name, task_id=task.task_id, success=False, error="Save returned no voice_id")

        await asyncio.sleep(1)

        # TTS sample
        sample_path = await self._tts_sample(client, voice_name, voice_id, spec)

        # Write to code
        written = self._write_voice_id(voice_name, voice_id)

        return AgentResult(
            agent_name=self.name,
            task_id=task.task_id,
            success=True,
            output={
                "voice_name": voice_name,
                "voice_id": voice_id,
                "sample_path": sample_path,
                "written_to_code": written,
            },
        )

    async def _op_search_library(self, task: AgentTask, client: httpx.AsyncClient) -> AgentResult:
        """Search ElevenLabs shared voice library."""
        query = task.params.get("query", "") or task.instruction
        results = await self._search_library(client, query)
        return AgentResult(
            agent_name=self.name,
            task_id=task.task_id,
            success=True,
            output={"query": query, "results": results, "count": len(results)},
        )

    async def _op_audition(self, task: AgentTask, client: httpx.AsyncClient) -> AgentResult:
        """Generate TTS sample for a voice."""
        voice_name = task.params.get("voice_name", "")
        voice_id = task.params.get("voice_id", "")

        if not voice_id and voice_name:
            # Look up from current status
            status = self._get_current_status()
            if voice_name in status and status[voice_name]["voice_id"]:
                voice_id = status[voice_name]["voice_id"]

        if not voice_id:
            return AgentResult(agent_name=self.name, task_id=task.task_id, success=False, error="No voice_id provided or found")

        spec = EDUCATION_VOICE_SPECS.get(voice_name, {"sample_text": "Hello, this is a voice test.", "model": "eleven_turbo_v2"})
        sample_path = await self._tts_sample(client, voice_name or "test", voice_id, spec)

        return AgentResult(
            agent_name=self.name,
            task_id=task.task_id,
            success=sample_path is not None,
            output={"voice_id": voice_id, "sample_path": sample_path},
        )

    async def _op_list_voices(self, task: AgentTask, client: httpx.AsyncClient) -> AgentResult:
        """List all voices in ElevenLabs account."""
        voices = await self._list_account_voices(client)
        cipher_voices = [v for v in voices if "cipher" in v.get("name", "").lower()]
        return AgentResult(
            agent_name=self.name,
            task_id=task.task_id,
            success=True,
            output={
                "total_voices": len(voices),
                "cipher_voices": cipher_voices,
                "all_voices": voices,
            },
        )
