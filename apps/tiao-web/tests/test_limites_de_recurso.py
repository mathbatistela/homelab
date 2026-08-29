"""The two files that declare the container's size have to agree.

``apps/tiao-web/app.yml`` describes the sizing; the Ansible role's defaults are
what actually becomes ``deploy.resources.limits`` on the VM. Until this test
existed the only thing linking them was a prose comment in each pointing at the
other, so editing one number and not the other passed the whole suite and the
declared sizing and the enforced sizing drifted apart silently.

Parsed with a targeted regex rather than a YAML library on purpose: both keys
are plain top-level-ish scalars, and the alternative is a new dependency the
app does not otherwise need. A key that stops matching fails the test loudly —
it never quietly compares nothing.
"""

import re
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[3]
APP_YML = RAIZ / "apps" / "tiao-web" / "app.yml"
DEFAULTS_YML = RAIZ / "ansible" / "roles" / "tiao_web" / "defaults" / "main.yml"


def _escalar(caminho: Path, chave: str) -> str:
    texto = caminho.read_text(encoding="utf-8")
    achados = re.findall(rf"^\s*{re.escape(chave)}:\s*(.+?)\s*$", texto, re.MULTILINE)
    achados = [a for a in achados if not a.startswith("#")]
    assert achados, f"{chave} nao encontrada em {caminho}"
    assert len(achados) == 1, f"{chave} aparece {len(achados)} vezes em {caminho}"
    return achados[0].strip().strip('"').strip("'")


@pytest.fixture(scope="module", autouse=True)
def arquivos_existem():
    assert APP_YML.is_file(), APP_YML
    assert DEFAULTS_YML.is_file(), DEFAULTS_YML


def test_memoria_declarada_e_a_memoria_aplicada():
    assert _escalar(APP_YML, "memory") == _escalar(DEFAULTS_YML, "tiao_web_memory_limit")


def test_cpu_declarada_e_a_cpu_aplicada():
    # Comparado como numero: "0.25" e 0.25 sao a mesma cota, e o role cita o
    # valor entre aspas porque o Ansible senao entrega um float pro template.
    assert float(_escalar(APP_YML, "cpus")) == float(
        _escalar(DEFAULTS_YML, "tiao_web_cpu_limit")
    )
