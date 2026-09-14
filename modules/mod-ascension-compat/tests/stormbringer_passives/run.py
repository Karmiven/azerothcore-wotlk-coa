"""Exercise Cloudburst and Shock's actual callbacks, including the triggered repeat."""
import argparse
import importlib.util
from pathlib import Path
import re
import struct
import tempfile

ROOT = Path(__file__).resolve().parents[4]
HARNESS = r'''
#include <cassert>
#include <cstdint>
#include <initializer_list>
#include <array>
#include <set>
#include <vector>
using uint32 = std::uint32_t;
using uint8 = std::uint8_t;
using uint64 = std::uint64_t;
// NATIVE_CLASSES
constexpr int ALLSPELLHOOK_ON_CAST = 1, ALLSPELLHOOK_ON_HIT_RESULT = 2,
    GLOBALHOOK_ON_LOAD_SPELL_CUSTOM_ATTR = 3, EFFECT_1 = 1, SPELL_MISS_NONE = 0;
struct SpellInfo
{uint32 Id = 801838, SpellFamilyName = 22;struct Slot {uint32 Effect = 0;};std::array<Slot,3> Effects;};
struct Unit;
struct Spell
{
    bool triggered = false;Unit* owner = nullptr;SpellInfo* info = nullptr;uint64 marker = 0;
    bool IsTriggered() const { return triggered; }
    Unit* GetCaster() const {return owner;}SpellInfo const* GetSpellInfo() const {return info;}
    uint64 GetScriptValue(uint32) const {return marker;}void SetScriptValue(uint32,uint64 value){marker=value;}
};
struct SpellMgr
{
    uint32 GetFirstSpellInChain(uint32 id) const
    {return ((id>=503326 && id<=503332)||id==504634) ? 804020 : id;}
} manager;
SpellMgr* sSpellMgr = &manager;
struct Player;
struct Unit {bool friendly=false;virtual ~Unit() = default;virtual Player* ToPlayer() { return nullptr; }};
struct Player : Unit
{
    uint32 cls = CLASS_STORMBRINGER;
    std::vector<uint32> casts;
    std::set<uint32> known, auras;
    Player* ToPlayer() override { return this; }
    uint32 getClass() const { return cls; }
    bool HasSpell(uint32 id) const {return known.contains(id);}bool HasAura(uint32 id) const {return auras.contains(id);}
    bool IsFriendlyTo(Unit* unit) const {return unit->friendly;}
    void CastSpell(Unit* target, uint32 id, bool triggered)
    {
        assert(target == this && triggered);
        casts.push_back(id);
    }
};
struct AllSpellScript
{
    AllSpellScript(char const*, std::initializer_list<int>) { }
    virtual void OnSpellCast(Spell*, Unit*, SpellInfo const*, bool) { }
    virtual void OnSpellHitResult(Spell*, Unit*, uint8, uint32, uint32, bool) { }
};
struct GlobalScript
{GlobalScript(char const*,std::initializer_list<int>){}virtual void OnLoadSpellCustomAttr(SpellInfo*){}};
// ACTUAL_SOURCE
int main()
{
    Player player;
    Unit creature;
    Spell spell;
    SpellInfo info;
    stormbringer_talent_casts hook;
    hook.OnSpellCast(&spell, &player, &info, false);
    assert(player.casts == std::vector<uint32>{802385});
    info.Id = 802385;
    hook.OnSpellCast(&spell, &player, &info, false);
    info.Id = 801838;
    spell.triggered = true;
    hook.OnSpellCast(&spell, &player, &info, false);
    spell.triggered = false;
    info.SpellFamilyName = 3;
    hook.OnSpellCast(&spell, &player, &info, false);
    info.SpellFamilyName = 22;
    player.cls = CLASS_MAGE;
    hook.OnSpellCast(&spell, &player, &info, false);
    hook.OnSpellCast(&spell, &creature, &info, false);
    hook.OnSpellCast(&spell, nullptr, &info, false);
    assert(player.casts.size() == 1);
    player.cls = CLASS_STORMBRINGER;
    for(uint32 id : {804020u,503326u,503327u,503328u,503329u,503330u,503331u,503332u,504634u,570054u})
    {
        player.casts.clear();player.known.clear();player.auras.clear();
        info.Id=id;info.SpellFamilyName=22;spell.info=&info;spell.owner=&player;spell.marker=0;
        spell.triggered=id==570054;
        hook.OnSpellHitResult(&spell,&creature,0,100,0,false);assert(player.casts.empty());
        player.auras.insert(500040); // An aura with this ID is not the learned-spell gate.
        hook.OnSpellHitResult(&spell,&creature,0,100,0,false);assert(player.casts.empty());
        player.known.insert(500040);player.auras.insert(800098);
        hook.OnSpellHitResult(&spell,&creature,0,100,0,false);assert(player.casts.empty());
        player.auras.erase(800098);
        hook.OnSpellHitResult(&spell,&creature,1,100,0,false);
        hook.OnSpellHitResult(&spell,&player,0,100,0,false);
        creature.friendly=true;hook.OnSpellHitResult(&spell,&creature,0,100,0,false);creature.friendly=false;
        assert(player.casts.empty());
        hook.OnSpellHitResult(&spell,&creature,0,100,0,false);
        hook.OnSpellHitResult(&spell,&creature,0,100,0,true);
        assert(player.casts==std::vector<uint32>{804086});
    }
    info.Id=804020;spell.triggered=true;spell.marker=0;player.casts.clear();
    hook.OnSpellHitResult(&spell,&creature,0,100,0,false);assert(player.casts.empty());
    info.Id=570054;info.SpellFamilyName=3;
    hook.OnSpellHitResult(&spell,&creature,0,100,0,false);assert(player.casts.empty());
    info.SpellFamilyName=22;player.cls=CLASS_MAGE;
    hook.OnSpellHitResult(&spell,&creature,0,100,0,false);assert(player.casts.empty());
    stormbringer_resource_contracts contracts;
    info.Effects[0].Effect=2;info.Effects[1].Effect=64;
    contracts.OnLoadSpellCustomAttr(&info);assert(info.Effects[0].Effect==2 && !info.Effects[1].Effect);
    info.Id=804020;info.Effects[1].Effect=64;
    contracts.OnLoadSpellCustomAttr(&info);assert(info.Effects[1].Effect==64);
}
'''


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace-tools", type=Path, default=ROOT.parent / "tools")
    parser.add_argument("--spell-dbc", type=Path)
    args = parser.parse_args()
    spec = importlib.util.spec_from_file_location("storm_compile", args.workspace_tools / "Test-LocalLoginCollections.py")
    native = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(native)
    classes = native.extractor.extract((ROOT / "src/server/shared/SharedDefines.h").read_text(), r"enum Classes\b")
    source = (ROOT / "modules/mod-ascension-compat/src/AscensionStormbringerTalents.cpp").read_text()
    code = HARNESS.replace("// NATIVE_CLASSES", classes + ";")
    code = code.replace("// ACTUAL_SOURCE", re.sub(r"^#include.*\n", "", source, flags=re.M))
    with tempfile.TemporaryDirectory(prefix="coa-stormbringer-passives-") as directory:
        native.OUT = Path(directory)
        result = native.compile_run(code, "stormbringer-passives")
        assert result.returncode == 0, result.stdout + result.stderr
    if args.spell_dbc:
        raw = args.spell_dbc.read_bytes()
        count = struct.unpack_from("<I", raw, 4)[0]
        rows = {r[0]: r for r in struct.iter_unpack("<234I", raw[20:20 + count * 936])
                if r[0] in {801838, 802385, 570054, 804086, 500040}}
        parent, child = rows[801838], rows[802385]
        assert parent[71:74] == (3, 64, 0) and parent[92] == 0 and parent[117] == 32991
        assert parent[208:212] == child[208:212] == (22, 0, 0, 8388608)
        assert child[71:74] == (98, 0, 0) and child[86] == 18 and child[89] == 16
        assert child[110] == 180 and child[80] + child[74] == 101 and child[92] == 45
        assert rows[570054][72] == 64 and rows[570054][117] == 804084
        assert rows[804086][72] == 175 and rows[804086][111] == 20 and rows[804086][117] == 803102
        assert rows[500040][71] == 2  # Call Lightning is a learned attack, not a gating aura.
        raw = (args.spell_dbc.parent / "SpellRadius.dbc").read_bytes()
        count = struct.unpack_from("<I", raw, 4)[0]
        radius = {r[0]: r[1] for r in struct.iter_unpack("<I3f", raw[20:20 + count * 16])}
        assert radius[45] == 10
    print("PASS: Cloudburst; Shock ranks/repeat, learned-spell gate, ward/hostile/miss/trigger guards and helper data")


if __name__ == "__main__":
    main()
