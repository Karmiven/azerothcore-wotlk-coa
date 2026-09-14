int main()
{
    struct Case { uint8 cls; uint32 first, last, resource; int32 amount; bool cast, each; };
    std::vector<Case> cases = {
        {14, 524706, 524706, 800058, 1, false, false},
        {14, 805240, 805240, 800058, 1, false, true},
        {16, 501421, 501432, 803102, 20, false, false},
        {16, 801844, 801844, 803102, 20, false, false},
        {16, 807105, 807111, 803102, 25, false, false},
        {16, 500043, 500043, 803102, 10, true, false},
        {16, 500925, 500925, 803102, 40, true, false},
        {16, 500927, 500927, 803102, 20, true, false},
        {16, 560032, 560032, 803102, 50, true, false},
        {17, 806869, 806874, 500906, 2, false, false},
        {17, 520005, 520005, 500906, 1, false, false},
    };
    ResourceService service;
    for (Case const& test : cases)
        for (uint32 id = test.first; id <= test.last; ++id)
        {
            Player player, enemy;
            player.cls = test.cls;
            Spell spell{&player, {id}};
            spell.triggered = true;
            service.OnSpellCast(&spell);
            service.OnSpellHitResult(&spell, &enemy, 0, 100, false);
            assert(player.Count(test.resource) == 0);
            spell.triggered = false;
            service.OnSpellHitResult(&spell, &player, 0, 100, false);
            enemy.friendly = true;
            service.OnSpellHitResult(&spell, &enemy, 0, 100, false);
            enemy.friendly = false;
            service.OnSpellHitResult(&spell, &enemy, 1, 100, false);
            assert(player.Count(test.resource) == 0);
            if (test.each)
            {
                service.OnSpellHitResult(&spell, &enemy, 0, 0, false);
                assert(player.Count(test.resource) == 0); // Gaze requires actual damage.
            }
            service.OnSpellHitResult(&spell, &enemy, 0, 100, false);
            assert(player.Count(test.resource) == (test.cast ? 0 : test.amount));
            service.OnSpellCast(&spell);
            assert(player.Count(test.resource) == test.amount);
            service.OnSpellHitResult(&spell, &enemy, 0, 100, true);
            assert(player.Count(test.resource) == test.amount * (test.each ? 2 : 1));

            // Existing native aura caps remain in force across distinct casts.
            int32 cap = test.resource == 803102 ? 100 : 6;
            player.AddAura(test.resource, &player)->m_stackAmount = cap - 1;
            Spell next{&player, {id}};
            service.OnSpellHitResult(&next, &enemy, 0, 100, false);
            service.OnSpellCast(&next);
            assert(player.Count(test.resource) == cap);

            player.auras.clear();
            player.cls = 8;
            Spell wrongClass{&player, {id}};
            service.OnSpellHitResult(&wrongClass, &enemy, 0, 100, false);
            service.OnSpellCast(&wrongClass);
            assert(player.Count(test.resource) == 0);
            if (test.cls == 16)
            {
                player.cls = 16;
                player.AddAura(800098, &player);
                Spell ward{&player, {id}};
                service.OnSpellHitResult(&ward, &enemy, 0, 100, false);
                service.OnSpellCast(&ward);
                assert(player.Count(803102) == 0);
            }
        }
    // Baseline native/helper paths must not gain a second grant from this table.
    struct Control { uint8 cls; uint32 id; };
    for (auto const& test : std::vector<Control>{
        {14, 801901}, {14, 501257}, {14, 547210}, {14, 801312}, {14, 501281},
        {14, 500610}, {14, 500761}, {14, 500762}, {14, 802075}, {14, 805239}, {14, 803476},
        {14, 707901}, {14, 707902}, {14, 707903}, {14, 712483}, {16, 804826},
        {17, 805671}, {17, 560664}, {17, 805669}})
    {
        Player player, enemy;
        player.cls = test.cls;
        Spell spell{&player, {test.id}};
        service.OnSpellHitResult(&spell, &enemy, 0, 100, false);
        service.OnSpellCast(&spell);
        assert(player.Count(800058) == 0 && player.Count(803102) == 0 && player.Count(500906) == 0);
    }
}
