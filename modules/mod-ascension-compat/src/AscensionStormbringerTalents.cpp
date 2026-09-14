/* Copyright (C) 2016+ AzerothCore, GNU AGPL v3. */
#include "Player.h"
#include "ScriptMgr.h"
#include "Spell.h"
#include "SpellMgr.h"

namespace
{
enum StormbringerTalentSpells : uint32
{
    SPELL_CLOUDBURST = 801838,
    SPELL_CLOUDBURST_KNOCKBACK = 802385,
    SPELL_SHOCK = 804020,
    SPELL_PERPETUAL_SHOCK = 570054,
    SPELL_CALL_LIGHTNING = 500040,
    SPELL_THUNDER_WARD = 800098,
    SPELL_STATIC = 803102,
    SPELL_GENERATE_STATIC_20 = 804086
};

class stormbringer_talent_casts : public AllSpellScript
{
public:
    stormbringer_talent_casts() : AllSpellScript("stormbringer_talent_casts",
        {ALLSPELLHOOK_ON_CAST, ALLSPELLHOOK_ON_HIT_RESULT}) { }

    void OnSpellCast(Spell* spell, Unit* caster, SpellInfo const* info, bool) override
    {
        Player* player = caster ? caster->ToPlayer() : nullptr;
        if (player && player->getClass() == CLASS_STORMBRINGER && info->SpellFamilyName == 22 &&
            info->Id == SPELL_CLOUDBURST && !spell->IsTriggered())
            // The active spell has a zero-radius dummy. Its separate native
            // helper supplies the ten-yard area and authored knockback speeds.
            player->CastSpell(player, SPELL_CLOUDBURST_KNOCKBACK, true);
    }

    void OnSpellHitResult(Spell* spell, Unit* target, uint8 miss, uint32, uint32, bool) override
    {
        Player* player = spell->GetCaster()->ToPlayer();
        SpellInfo const* info = spell->GetSpellInfo();
        if (!player || player->getClass() != CLASS_STORMBRINGER || info->SpellFamilyName != 22 ||
            !target || target == player || player->IsFriendlyTo(target) || miss != SPELL_MISS_NONE ||
            !player->HasSpell(SPELL_CALL_LIGHTNING) || player->HasAura(SPELL_THUNDER_WARD))
            return;
        bool repeat = info->Id == SPELL_PERPETUAL_SHOCK;
        if ((!repeat && (spell->IsTriggered() || sSpellMgr->GetFirstSpellInChain(info->Id) != SPELL_SHOCK)) ||
            spell->GetScriptValue(SPELL_STATIC))
            return;
        spell->SetScriptValue(SPELL_STATIC, 1);
        player->CastSpell(player, SPELL_GENERATE_STATIC_20, true);
    }
};

class stormbringer_resource_contracts : public GlobalScript
{
public:
    stormbringer_resource_contracts() : GlobalScript("stormbringer_resource_contracts",
        {GLOBALHOOK_ON_LOAD_SPELL_CUSTOM_ATTR}) { }

    void OnLoadSpellCustomAttr(SpellInfo* info) override
    {
        if (info && info->Id == SPELL_PERPETUAL_SHOCK && info->SpellFamilyName == 22)
            // The hit callback supplies the learned-spell gate and one 20-Static grant.
            info->Effects[EFFECT_1].Effect = 0;
    }
};
}

void AddSC_AscensionStormbringerTalents()
{
    new stormbringer_talent_casts();
    new stormbringer_resource_contracts();
}
