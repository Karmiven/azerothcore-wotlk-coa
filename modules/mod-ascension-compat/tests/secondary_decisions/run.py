"""Execute the approved Warpath metadata with the existing native fixture."""
import argparse
import importlib.util
from pathlib import Path
import struct
import tempfile

ROOT = Path(__file__).resolve().parents[4]
CASES = r'''
int main()
{
    SpellInfo warpath;
    warpath.Id = SPELL_WARPATH_PROTECTION;
    warpath.Effects[0].Effect = SPELL_EFFECT_APPLY_AURA;
    warpath.Effects[0].ApplyAuraName = SPELL_AURA_MOD_MINIMUM_SPEED;
    warpath.Effects[0].BasePoints = 89;
    warpath.DurationEntry = sSpellDurationStore.LookupEntry(21);
    ApplyContracts(&warpath);
    assert(warpath.DurationEntry->ID == 27 && warpath.Effects[0].CalcValue() == 90);
    warpath.SpellFamilyName = 3;
    warpath.DurationEntry = sSpellDurationStore.LookupEntry(21);
    ApplyContracts(&warpath);
    assert(warpath.DurationEntry->ID == 21);

}
'''


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--workspace-tools', type=Path, default=ROOT.parent / 'tools')
    parser.add_argument('--spell-dbc', type=Path, required=True)
    args = parser.parse_args()
    spec = importlib.util.spec_from_file_location('xoroth_fixture',
                                                args.workspace_tools / 'Test-KnightOfXorothCompletion.py')
    fixture = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(fixture)
    fixture.M = ROOT / 'modules/mod-ascension-compat/src'
    production = ''
    production += fixture.native.extractor.extract(fixture.src('Contracts'), r'enum FleshHook\b') + ';\n'
    production += 'namespace AscensionXoroth {' + fixture.methods('Contracts', ['ApplyContracts']) + '}\n'
    code = fixture.fixture().replace('/*PRODUCTION*/', production).replace('/*CASES*/', CASES)
    code = code.replace('struct SpellInfo {', 'struct SpellRangeEntry {uint32 ID = 0;}; '
                        'Store<SpellRangeEntry> sSpellRangeStore; struct SpellInfo { '
                        'SpellRangeEntry const* RangeEntry = nullptr; ')
    with tempfile.TemporaryDirectory(prefix='coa-secondary-decisions-') as directory:
        fixture.native.OUT = Path(directory)
        result = fixture.native.compile_run(code, 'decisions')
        assert result.returncode == 0, result.stdout + result.stderr
    raw = (args.spell_dbc.parent / 'SpellDuration.dbc').read_bytes()
    count, fields, width, _ = struct.unpack_from('<4I', raw, 4)
    assert (fields, width) == (4, 16)
    rows = {r[0]: r[1:] for r in struct.iter_unpack('<Iiii', raw[20:20 + count * width])}
    assert rows[27] == (3000, 0, 3000)
    print('PASS: Warpath 90% floor/3 seconds')


if __name__ == '__main__':
    main()
