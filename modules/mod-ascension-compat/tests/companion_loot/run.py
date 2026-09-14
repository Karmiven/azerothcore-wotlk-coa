"""Compile actual loot-view serialization and companion collection against bounded API fixtures."""
import os
from pathlib import Path
import runpy
import subprocess
import tempfile

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
method = runpy.run_path(str(HERE.parent / "client_compat/run.py"))["method"]


def main():
    player = (ROOT / 'src/server/game/Entities/Player/Player.cpp').read_text(encoding='utf-8')
    storage = (ROOT / 'src/server/game/Entities/Player/PlayerStorage.cpp').read_text(encoding='utf-8')
    loot = (ROOT / 'src/server/game/Loot/LootMgr.cpp').read_text(encoding='utf-8')
    header = (ROOT / 'src/server/game/Loot/LootMgr.h').read_text(encoding='utf-8')
    compat = (ROOT / 'modules/mod-ascension-compat/src/AscensionCompat.cpp').read_text(encoding='utf-8')
    code = r'''
#include <cassert>
#include <cstdint>
#include <cstring>
#include <map>
#include <array>
#include <list>
#include <memory>
#include <unordered_set>
#include <vector>
#include <type_traits>
using uint8=std::uint8_t;using uint32=std::uint32_t;using uint64=std::uint64_t;
struct ObjectGuid
{
    uint64 id=0;explicit operator bool()const{return id!=0;}void Clear(){id=0;}
    bool operator==(ObjectGuid b)const{return id==b.id;}bool operator!=(ObjectGuid b)const{return id!=b.id;}
    bool operator<(ObjectGuid b)const{return id<b.id;}
};
struct ByteBuffer
{
    std::vector<uint8> bytes;std::size_t cursor=0;
    template<class T, std::enable_if_t<std::is_arithmetic_v<T>,int> =0>
    ByteBuffer& operator<<(T v)
    {auto p=reinterpret_cast<uint8*>(&v);bytes.insert(bytes.end(),p,p+sizeof v);return *this;}
    ByteBuffer& operator<<(ObjectGuid v){return *this<<v.id;}
    template<class T> ByteBuffer& operator>>(T& v)
    {assert(cursor+sizeof v<=bytes.size());std::memcpy(&v,bytes.data()+cursor,sizeof v);cursor+=sizeof v;return *this;}
    void rpos(std::size_t p){cursor=p;}std::size_t wpos()const{return bytes.size();}
    void read_skip(std::size_t n){cursor+=n;assert(cursor<=bytes.size());}
    template<class T> void read_skip(){read_skip(sizeof(T));}
    template<class T> void put(std::size_t p,T v)
    {assert(p+sizeof v<=bytes.size());std::memcpy(bytes.data()+p,&v,sizeof v);}
};
using WorldPacket=ByteBuffer;
'''
    for enum in ('LootMethod', 'PermissionTypes', 'LootType', 'LootSlotType'):
        code += method(header, 'enum ' + enum) + ';\n'
    code += r'''
constexpr uint32 PLAYER_FLAGS_NO_PLAY_TIME=1;
constexpr float INTERACTION_DISTANCE=5;
enum InventoryResult{EQUIP_ERR_OK,EQUIP_ERR_INVENTORY_FULL};
struct Player;struct Creature;
struct Group{LootMethod method=GROUP_LOOT;ObjectGuid master{1};LootMethod GetLootMethod()const{return method;}
    ObjectGuid GetMasterLooterGuid()const{return master;}};
struct LootItem
{
    uint32 itemid=1,count=1,randomSuffix=0,randomPropertyId=0;
    bool is_looted=false,freeforall=false,is_blocked=false,is_underthreshold=true,follow_loot_rules=false;
    ObjectGuid rollWinnerGUID;std::vector<int> conditions;
    bool AllowedForPlayer(Player*,ObjectGuid)const{return true;}
};
struct QuestItem{uint8 index;bool is_looted=false;};
using QuestItemList=std::vector<QuestItem>;using QuestItemMap=std::map<ObjectGuid,QuestItemList*>;
struct Loot
{
    std::vector<LootItem> items,quest_items;uint32 gold=12;ObjectGuid roundRobinPlayer,sourceWorldObjectGUID{3};
    LootType loot_type=LOOT_CORPSE;QuestItemMap quests,ffa,conditional;
    bool isLooted()const{return false;}bool hasItemForAll()const{return true;}
    bool hasItemFor(Player const*)const{return true;}
    bool hasOverThresholdItem()const{return true;}
    QuestItemMap const& GetPlayerQuestItems()const{return quests;}
    QuestItemMap const& GetPlayerFFAItems()const{return ffa;}
    QuestItemMap const& GetPlayerNonQuestNonFFAConditionalItems()const{return conditional;}
};
struct Creature
{
    ObjectGuid guid{3},owner{1};bool alive=false,inRange=true,los=true,reward=true;
    Player* recipient=nullptr;Group* group=nullptr;
    Loot loot;std::list<Creature*> nearby;
    void GetDeadCreatureListInGrid(std::list<Creature*>& out,float radius,bool deadOnly)const
    {assert(radius==40 && deadOnly);out=nearby;}
    ObjectGuid GetGUID()const{return guid;}ObjectGuid GetOwnerGUID()const{return owner;}
    bool IsAlive()const{return alive;}
    bool isDead()const{return !alive;}bool IsDamageEnoughForLootingAndReward()const{return reward;}
    bool IsLootRewardDisabled()const{return false;}Player* GetLootRecipient()const{return recipient;}
    Group* GetLootRecipientGroup()const{return group;}ObjectGuid GetLootRecipientGUID()const{return owner;}
    bool IsWithinDistInMap(Player const*,float radius)const{return inRange && radius>5;}
    bool IsWithinDistInMap(Creature const*,float)const{return inRange;}
    bool IsWithinLOSInMap(Creature const*)const{return los;}
};
struct Map{Creature* pet=nullptr;Creature* GetCreature(ObjectGuid)const{return pet;}};
struct Session
{
    Player* player;uint32 moneyCalls=0,releases=0;
    void HandleLootMoneyOpcode(WorldPacket&);void DoLootRelease(ObjectGuid);
};
struct Player
{
    bool alive=true,inWorld=true,restricted=false,full=false;uint32 resetChecks=0;
    Map map;Session session{this};Session* m_session=&session;ObjectGuid lootGuid,m_companionLootGuid;
    Creature* current=nullptr;Group* group=nullptr;PermissionTypes permission=OWNER_PERMISSION;
    std::vector<uint8> stored;
    bool IsAlive()const{return alive;}bool IsInWorld()const{return inWorld;}
    bool HasPlayerFlag(uint32)const{return restricted;}
    ObjectGuid GetGUID()const{return {1};}ObjectGuid GetCritterGUID()const{return {2};}
    ObjectGuid GetLootGUID()const{return lootGuid;}
    Map* GetMap(){return &map;}Group* GetGroup()const{return group;}bool HasPendingBind()const{return false;}
    bool HasQuestForItem(uint32,int,bool,bool*){return true;}
    void StoreLootItem(uint8 slot,Loot* l,InventoryResult& result)
    {
        result=full?EQUIP_ERR_INVENTORY_FULL:EQUIP_ERR_OK;
        if(!full){stored.push_back(slot);if(slot<l->items.size())l->items[slot].is_looted=true;}
    }
    bool isAllowedToLoot(Creature const*);
    bool IsWithinLootDistance(Creature const*)const;
    void LootCreatureWithCompanion(Creature*,float);
    void SendLoot(ObjectGuid,LootType);
};
struct Scripts{void OnPlayerAfterCreatureLoot(Player*){}} scripts;
auto sScriptMgr=&scripts;
struct Template{uint32 DisplayInfoID=100;};
constexpr uint32 EFFECT_0=0;
struct Effect{uint32 Amplitude=1000;float CalcRadius(Player*)const{return 40;}};
struct SpellInfo{std::array<Effect,1> Effects;};
struct Manager{Template row;SpellInfo spell;Template* GetItemTemplate(uint32){return &row;}
    SpellInfo const* GetSpellInfo(uint32 id)const{assert(id==84419);return &spell;}} manager;
auto sObjectMgr=&manager;
auto sSpellMgr=&manager;
'''
    code += method(header, 'struct LootView\n{') + ';\n'
    code += method(loot, 'ByteBuffer& operator<<(ByteBuffer& b, LootItem const& li)')
    # Native LootView already converts its enum to uint8 implicitly. Keep warnings strict for new code.
    code += '\n#pragma warning(push)\n#pragma warning(disable:4244)\n'
    code += method(loot, 'ByteBuffer& operator<<(ByteBuffer& b, LootView const& lv)')
    code += '\n#pragma warning(pop)\n'
    code += method(storage, 'bool Player::isAllowedToLoot(')
    code += method(player, 'bool Player::IsWithinLootDistance(')
    code += method(player, 'void Player::LootCreatureWithCompanion(')
    code += r'''
void Player::SendLoot(ObjectGuid guid,LootType lootType)
{
    assert(current && IsWithinLootDistance(current));lootGuid=guid;Loot* loot=&current->loot;
    WorldPacket data;data<<guid<<uint8(lootType)<<LootView(*loot,this,permission);
'''
    code += method(player, 'if (guid == m_companionLootGuid)') + '\n}\n'
    code += method(compat, 'enum CompanionLoot') + ';\n'
    code += r'''
struct State
{
    std::array<uint32,69> ActiveAppearances{};std::unordered_set<uint32> CollectedAppearances;
    uint32 CompanionLootTimer=0;
};
struct Cosmetics
{
    std::shared_ptr<State> collection=std::make_shared<State>();
    std::shared_ptr<State> GetState(Player*){return collection;}
'''
    code += method(compat, 'void ProcessCompanionLoot(') + '};\n'
    code += r'''
void Session::HandleLootMoneyOpcode(WorldPacket&)
{assert(player->IsWithinLootDistance(player->current));++moneyCalls;player->current->loot.gold=0;}
void Session::DoLootRelease(ObjectGuid guid)
{
    assert(player->IsWithinLootDistance(player->current));assert(guid==player->lootGuid);
    ++releases;player->lootGuid.Clear();
}
struct Case
{
    Player player;Creature pet,corpse;Group group;
    Case(){pet.guid={2};pet.alive=true;corpse.recipient=&player;player.map.pet=&pet;player.current=&corpse;
        corpse.loot.items.resize(3);}
    void collect(){player.LootCreatureWithCompanion(&corpse,40);assert(!player.m_companionLootGuid);}
};
int main()
{
    {Case c;Cosmetics cosmetics;c.pet.nearby={&c.corpse};
        cosmetics.ProcessCompanionLoot(&c.player,1);assert(c.player.stored.empty());
        cosmetics.collection->ActiveAppearances[38]=47520;
        cosmetics.ProcessCompanionLoot(&c.player,1);assert(c.player.stored.empty());
        cosmetics.collection->CollectedAppearances.insert(47520);
        cosmetics.ProcessCompanionLoot(&c.player,1);assert(c.player.stored.size()==3);
        cosmetics.ProcessCompanionLoot(&c.player,999);assert(c.player.session.moneyCalls==1);
        cosmetics.ProcessCompanionLoot(&c.player,1);assert(c.player.session.moneyCalls==2);
        cosmetics.collection->ActiveAppearances[38]=0;
        cosmetics.ProcessCompanionLoot(&c.player,1000);assert(c.player.session.moneyCalls==2);}
    {Case c;c.collect();assert((c.player.stored==std::vector<uint8>{0,1,2}));assert(c.player.session.moneyCalls==1);
        assert(c.player.session.releases==1 && !c.player.IsWithinLootDistance(&c.corpse));}
    {Case c;c.player.full=true;c.collect();assert(c.player.stored.empty() && !c.corpse.loot.items[0].is_looted);
        assert(c.corpse.loot.gold==0);}
    for(int gate=0;gate<11;++gate)
    {
        Case c;
        if(gate==0)c.pet.owner={9};if(gate==1)c.player.map.pet=nullptr;if(gate==2)c.pet.inRange=false;
        if(gate==3)c.pet.los=false;if(gate==4)c.player.restricted=true;if(gate==5)c.corpse.recipient=nullptr;
        if(gate==6)c.player.lootGuid={99};if(gate==7)c.corpse.loot.loot_type=LOOT_SKINNING;
        if(gate==8)c.player.alive=false;if(gate==9)c.player.inWorld=false;if(gate==10)c.pet.alive=false;
        c.collect();assert(c.player.stored.empty() && c.corpse.loot.gold==12);
    }
    {Case c;c.player.group=&c.group;c.corpse.group=&c.group;c.player.permission=GROUP_PERMISSION;
        c.corpse.loot.items[0].is_blocked=true;c.corpse.loot.items[1].rollWinnerGUID={9};
        c.collect();assert((c.player.stored==std::vector<uint8>{2}));}
    {Case c;c.player.group=&c.group;c.corpse.group=&c.group;c.player.permission=MASTER_PERMISSION;
        c.group.method=MASTER_LOOT;c.corpse.loot.items[0].is_blocked=true;
        c.collect();assert((c.player.stored==std::vector<uint8>{1,2}));}
    {Case c;c.player.group=&c.group;c.corpse.group=&c.group;c.player.permission=ROUND_ROBIN_PERMISSION;
        c.group.method=ROUND_ROBIN;c.corpse.loot.roundRobinPlayer={9};
        QuestItemList free{{1}};c.corpse.loot.items[1].freeforall=true;c.corpse.loot.ffa[{1}]=&free;
        c.collect();assert((c.player.stored==std::vector<uint8>{1}));}
    {Case c;c.player.group=&c.group;c.corpse.group=&c.group;c.player.permission=GROUP_PERMISSION;
        c.corpse.loot.quest_items.resize(2);c.corpse.loot.quest_items[0].follow_loot_rules=true;
        c.corpse.loot.quest_items[0].is_blocked=true;c.corpse.loot.quest_items[1].freeforall=true;
        QuestItemList quests{{0},{1}};c.corpse.loot.quests[{1}]=&quests;
        c.collect();assert((c.player.stored==std::vector<uint8>{0,1,2,4}));}
}
'''
    compiler = str(Path(os.environ['VCToolsInstallDir']) / 'bin/Hostx64/x64/cl.exe')
    with tempfile.TemporaryDirectory(prefix='coa-companion-loot-') as directory:
        out = Path(directory)
        cpp, exe = out / 'loot.cpp', out / 'loot.exe'
        cpp.write_text(code, encoding='utf-8')
        subprocess.run([compiler, '/nologo', '/std:c++20', '/EHsc', '/W4', '/WX', '/utf-8',
                        str(cpp), '/Fe' + str(exe)], cwd=out, check=True, timeout=60)
        subprocess.run([str(exe)], cwd=out, check=True, timeout=15)
    print('PASS: native loot-view permissions, group rolls, master loot, quest/FFA slots, full bags and scoped reach')


if __name__ == '__main__':
    main()
