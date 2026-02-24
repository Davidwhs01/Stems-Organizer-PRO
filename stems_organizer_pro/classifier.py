import os
import re
import json
import urllib.request
import subprocess
import hashlib
import logging
from collections import Counter
from google import genai
from google.genai import types

from stems_organizer_pro.config import RULES_URL, PROMPT_URL
from stems_organizer_pro.utils import retry_on_failure

logger = logging.getLogger(__name__)
MIN_PREFIX_OCCURRENCES = 3

class AudioClassifier:
    """Responsável por regras, análise de silêncio (FFmpeg) e classificação IA (Gemini)."""
    
    def __init__(self, api_key="", supabase_client=None, ffmpeg_available=True):
        self.api_key = api_key
        self.supabase = supabase_client
        self.ffmpeg_available = ffmpeg_available
        self.ia_cache = {}
        self.PARENT_FOLDER_MAP = {}
        self.LOCAL_CLASSIFICATION_RULES = {}
        self.master_prompt = ""

    def load_rules(self):
        """Carrega regras locais e mapeamentos do web ou fallback"""
        try:
            request = urllib.request.Request(RULES_URL)
            request.add_header('User-Agent', 'StemsOrganizerPro/1.0')
            with urllib.request.urlopen(request, timeout=15) as response:
                data = json.loads(response.read().decode('utf-8'))
                self.PARENT_FOLDER_MAP = data.get("parent_folder_map", {})
                self.LOCAL_CLASSIFICATION_RULES = data.get("local_classification_rules", {})
                logger.debug(f"Loaded {len(self.LOCAL_CLASSIFICATION_RULES)} rule categories")
        except Exception as e:
            logger.debug(f"Rules loading failed - {e}. Using fallback.")
            self.PARENT_FOLDER_MAP = {
                "Drums": "Rhythm", "Bass": "Rhythm", "Perc": "Rhythm",
                "GTRs": "Harmony", "Piano": "Harmony", "Synth": "Harmony", "Pad": "Harmony",
                "Vocal": "Melody", "Orchestra": "Melody", "Fx": "Effects"
            }
            self.LOCAL_CLASSIFICATION_RULES = {
                "Drums": ["drum", "kick", "snare", "hat", "hihat", "cymbal", "tom", "perc"],
                "Bass": ["bass", "sub", "low", "808"],
                "GTRs": ["guitar", "gtr", "strum", "chord"],
                "Vocal": ["vocal", "voice", "lead", "harmony", "choir"],
                "Synth": ["synth", "lead", "pluck", "arp"],
                "Pad": ["pad", "string", "atmosphere"],
                "Orchestra": ["orchestra", "violin", "cello", "brass"],
                "Piano": ["piano", "keys", "electric"],
                "Fx": ["fx", "effect", "ambient", "riser", "sweep"],
                "Perc": ["perc", "shaker", "tambourine", "conga"]
            }

        # Carregar do Supabase se existir
        if self.supabase:
            try:
                resp = self.supabase.table('ai_learning_rules').select('keyword', 'category').eq('is_approved', True).execute()
                learned_rules = resp.data if resp.data else []
                logger.debug(f"Loaded {len(learned_rules)} learned rules from Supabase.")
                for rule in learned_rules:
                    kw, cat = rule['keyword'], rule['category']
                    if cat in self.LOCAL_CLASSIFICATION_RULES:
                        if kw not in self.LOCAL_CLASSIFICATION_RULES[cat]:
                            self.LOCAL_CLASSIFICATION_RULES[cat].append(kw)
                    else:
                        self.LOCAL_CLASSIFICATION_RULES[cat] = [kw]
            except Exception as e:
                logger.debug(f"Erro ao buscar regras Supabase: {e}")
        
        return True

    def load_prompt(self):
        """Carrega prompt mestre da web ou fallback"""
        try:
            request = urllib.request.Request(PROMPT_URL)
            request.add_header('User-Agent', 'StemsOrganizerPro/1.0')
            with urllib.request.urlopen(request, timeout=15) as response:
                self.master_prompt = response.read().decode('utf-8')
                logger.debug("Master prompt loaded successfully")
                return True
        except Exception as e:
            logger.debug(f"Erro ao baixar prompt: {e}. Usando fallback.")
            self.master_prompt = """
Você é um especialista em classificação de stems musicais. Analise os nomes dos arquivos e classifique-os nas seguintes categorias:

CATEGORIAS VÁLIDAS:
- Drums: Elementos de bateria (kick, snare, hihat, cymbal, tom, etc.)
- Bass: Elementos de baixo frequência (bass, sub, 808, low, etc.) 
- GTRs: Guitarras e instrumentos de corda (guitar, gtr, strum, chord, etc.)
- Vocal: Elementos vocais (vocal, voice, lead, harmony, choir, etc.)
- Synth: Sintetizadores (synth, lead, pluck, arp, etc.)
- Pad: Pads e atmosferas (pad, string, atmosphere, etc.)
- Orchestra: Instrumentos orquestrais (orchestra, violin, cello, brass, etc.)
- Piano: Piano e teclados (piano, keys, electric, etc.)
- Fx: Efeitos sonoros (fx, effect, ambient, riser, sweep, etc.)
- Perc: Percussão (perc, shaker, tambourine, conga, etc.)
- Outros: Arquivos que não se encaixam em nenhuma categoria acima

ARQUIVOS PARA CLASSIFICAR:
{file_list}

INSTRUÇÕES:
1. Analise cada nome de arquivo cuidadosamente
2. Identifique palavras-chave que indiquem o tipo de instrumento/som
3. Classifique usando APENAS as categorias listadas acima
4. Retorne APENAS um JSON válido no formato: {{"nome_arquivo": "categoria"}}
5. Não adicione explicações ou texto extra

EXEMPLO DE RESPOSTA:
{{"kick_01.wav": "Drums", "bass_line.wav": "Bass", "guitar_chord.wav": "GTRs"}}

Categorias válidas: {valid_categories_list}
"""
            return True

    def get_cache_key(self, filename):
        return hashlib.md5(filename.lower().encode()).hexdigest()

    def get_cached_result(self, filename):
        return self.ia_cache.get(self.get_cache_key(filename))

    def cache_result(self, filename, category):
        self.ia_cache[self.get_cache_key(filename)] = category

    def should_discard(self, filename):
        discard_patterns = ["('_0)", "master.wav", ".tmp", "_backup", "_old"]
        return any(p in filename.lower() for p in discard_patterns)

    def classify_locally(self, filename):
        fl = filename.lower()
        for cat, keywords in self.LOCAL_CLASSIFICATION_RULES.items():
            if any(k.lower() in fl for k in keywords):
                return cat
        return None

    def find_common_prefix(self, files):
        if not files: return ""
        
        # Regex para capturar padrões comuns no início que devem ser cortados
        # Ex: "01 - Kick", "[120 BPM] Snare", "Stem_04_"
        padrao_sujeira = re.compile(
            r'^('
            r'\d+[\s\-_]*|'                          # "01 ", "01-", "01_"
            r'\[.*?\][\s\-_]*|'                      # "[120 BPM] ", "[Gmaj]"
            r'\(.*?\)[\s\-_]*|'                      # "(chorus) "
            r'(stem|track|audio)[\s\_]*\d*[\s\-_]*'   # "Stem 01 - "
            r')+', 
            re.IGNORECASE
        )
        
        # Na verdade, não tentaremos encontrar um "prefixo comum" rígido.
        # Nós vamos retornar uma função ou um prefixo estático melhor.
        # Por enquanto, mantemos a lógica de prefixo idêntico, 
        # mas permitimos que o main limpe a sujeira também.
        
        possibles = []
        for f in files:
            nl = f.strip()
            # Limpa prefixos isolados primeiro
            nl = padrao_sujeira.sub('', nl)
            
            for i in range(3, min(25, len(nl))):
                px = nl[:i]
                if px.endswith(('_', '-', ' ', '.')):
                    possibles.append(px)
        
        counter = Counter(possibles)
        for px, count in counter.most_common():
            # A palavra tem que aparecer em pelo menos 3 arquivos ou 30% dos arquivos
            if count >= max(MIN_PREFIX_OCCURRENCES, int(len(files)*0.3)):
                return px
        
        return ""

    def is_audio_silent(self, filepath, deep_check=False):
        if not self.ffmpeg_available:
            return False
            
        try:
            res = subprocess.run(['ffmpeg', '-i', filepath, '-af', 'volumedetect', '-f', 'null', 'NUL'], capture_output=True, text=True, timeout=30)
            out = res.stderr
            max_volume = None
            for line in out.split('\\n'):
                if 'max_volume' in line:
                    try:
                        if '-inf' in line:
                            max_volume = float('-inf')
                        else:
                            m = re.search(r'max_volume:\s*([-\d.]+)\s*dB', line)
                            if m: max_volume = float(m.group(1))
                    except ValueError:
                        continue
            
            if max_volume is None: return False
            if max_volume == float('-inf') or max_volume <= -70:
                logger.info(f"🔇 Silêncio detectado ({max_volume} dB): {os.path.basename(filepath)}")
                return True
            if deep_check and max_volume <= -60:
                logger.info(f"🔇 Silêncio profundo ({max_volume} dB): {os.path.basename(filepath)}")
                return True
            return False
        except Exception as e:
            logger.debug(f"Erro FFmpeg em {filepath}: {e}")
            return False

    @retry_on_failure(max_retries=3, delay=1.0, backoff=2.0)
    def classify_with_ai(self, files_list):
        if not files_list or not self.api_key:
            return {}
            
        cached = {}
        to_classify = []
        for f in files_list:
            c = self.get_cached_result(f)
            if c:
                cached[f] = c
            else:
                to_classify.append(f)
                
        if not to_classify: return cached
        
        try:
            val_cats = list(self.LOCAL_CLASSIFICATION_RULES.keys()) + ["Outros"]
            files_str = "\\n".join([f"- {x}" for x in to_classify])
            prompt = self.master_prompt.format(file_list=files_str, valid_categories_list=", ".join(val_cats))
            
            client = genai.Client(api_key=self.api_key)
            try:
                resp = client.models.generate_content(
                    model="gemini-flash-latest",
                    contents=prompt,
                    config=types.GenerateContentConfig(max_output_tokens=2048, temperature=0.1)
                )
            except Exception as api_err:
                err_str = str(api_err).lower()
                if "429" in err_str or "quota" in err_str:
                    logger.warning("Cota da API Gemini excedida (Error 429). Tentando aguardar 10s...")
                    import time
                    time.sleep(10)
                    resp = client.models.generate_content(
                        model="gemini-flash-latest",
                        contents=prompt,
                        config=types.GenerateContentConfig(max_output_tokens=2048, temperature=0.1)
                    )
                else:
                    raise api_err
            
            if not resp or not resp.text: return {}
            
            t = resp.text.strip()
            t = re.sub(r'^```(?:json|JSON)?\s*\n?', '', t)
            t = re.sub(r'\n?```\s*$', '', t).strip()
            
            try:
                res_json = json.loads(t)
            except json.JSONDecodeError:
                m = re.search(r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}', t)
                if m: res_json = json.loads(m.group())
                else: return {}
                
            validated = {}
            for f, cat in res_json.items():
                final_cat = cat if cat in val_cats else "Outros"
                validated[f] = final_cat
                self.cache_result(f, final_cat)
                
            validated.update(cached)
            return validated
            
        except Exception as e:
            logger.error(f"Erro classificação IA: {e}")
            raise
