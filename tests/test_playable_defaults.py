"""Defaults remain assumptions; dynamic probabilities use exact rational arithmetic."""

from collections import defaultdict
from dataclasses import replace
from fractions import Fraction
from itertools import combinations
from math import comb

import pytest

from astral_town.data.loader import load_builtin, load_file
from astral_town.model.building import BuildingInstance
from astral_town.model.board import Lot, Space
from astral_town.model.enums import SpaceType
from astral_town.model.enums import BuildingType as B, StandType as S, Pack, EventType as E, RuleConfidence as C
from astral_town.model.events import Event
from astral_town.model.stand import StandInstance
from astral_town.rules.catalog import eligible, required_packs
from astral_town.rules.stand_catalog import stand_eligible
from astral_town.rules.game import Game
from astral_town.rules.registry import RuleRegistry, RuleValue, UnresolvedRule
from astral_town.rules.randomness import configured_distribution
from astral_town.rules.rewards import building_from_template
from astral_town.scenario import from_scenario
from astral_town.solver.expectimax import Expectimax
from astral_town.solver.management_search import Action, apply_action
from astral_town.solver.rollout import rollout
from test_game import game_fixture
from test_prosperity import event
from test_promotion import template


def playable(extra=None):
    old, state = game_fixture()
    assumptions = dict(old.registry.assumptions)
    for key in load_builtin("assumptions_playable.json")["assumptions"]:assumptions.pop(key, None)
    assumptions.update(extra or {})
    registry = RuleRegistry.builtin(assumptions, profile="playable-defaults")
    board=replace(old.board,spaces=tuple(Space(i,SpaceType.START if i==0 else SpaceType.NORMAL,i-1 if 1<=i<=4 else None) for i in range(16)),
                  lots=tuple(Lot(i,frozenset(j for j in range(4) if abs(i-j)==1)) for i in range(4)))
    return Game(registry, board, accept_topology_assumption=True), replace(state,unlocked_lots=frozenset(range(4)))


def assert_fresh(building):
    assert replace(building,instance_id=0) == BuildingInstance(0,building.building_type)


@pytest.mark.parametrize("packs", [frozenset({Pack.PROSPERITY}), frozenset({Pack.LUCK}), frozenset(Pack)])
def test_card_uniform_dynamic_eligibility_and_fresh_state(packs):
    game, state = playable()
    state = replace(state,selected_packs=packs)
    rows = configured_distribution(game.registry,"card_distribution",state)
    pool = {kind for kind in B if eligible(kind,packs,game.registry)}
    assert {B(o.state["building_type"]) for o in rows} == pool
    assert all(o.probability == Fraction(1,len(pool)) for o in rows)
    assert sum(o.probability for o in rows) == 1
    for row in rows:assert_fresh(building_from_template(state,row.state,game.registry))
    assert game.registry.profile_assumptions_used == ("card_distribution","generated_building_state")


def test_same_registry_recomputes_pool_after_pack_change():
    game,state=playable()
    before=configured_distribution(game.registry,"card_distribution",replace(state,selected_packs=frozenset({Pack.PROSPERITY})))
    after=configured_distribution(game.registry,"card_distribution",replace(state,selected_packs=frozenset({Pack.PROSPERITY,Pack.LUCK})))
    assert B.LUCKY_COLOR_GATE not in {B(o.state['building_type']) for o in before}
    assert B.LUCKY_COLOR_GATE in {B(o.state['building_type']) for o in after}
    assert len(after)>len(before)


@pytest.mark.parametrize("packs", [frozenset({Pack.LUCK}), frozenset({Pack.LUCK,Pack.PIRATE}), frozenset(Pack)])
def test_three_leaf_rewards_only_eligible_luck_types(packs):
    game,state=playable({"stand_charge_consumption":"subtract"})
    state=replace(state,selected_packs=packs,stands=(StandInstance(20,S.THREE_LEAF,5),))
    results=game.engine.run(state,(Event(E.ACTIVATE_STAND,20,payload=(("trigger","die"),("face",6))),))
    pool={kind for kind in B if eligible(kind,packs,game.registry) and Pack.LUCK in required_packs(kind,game.registry)}
    assert {o.state.inventory[0].building_type for o in results} == pool
    assert all(o.probability==Fraction(1,len(pool)) for o in results)
    for o in results:
        assert_fresh(o.state.inventory[0])
        assert o.state.stands[0].charge==0


def test_fox_and_cannon_rewards_are_fresh_with_exact_probabilities():
    game,state=playable()
    state=replace(state,selected_packs=frozenset(Pack),buildings=(BuildingInstance(1,B.FOX_ANTIQUE_SHOP,location=0),))
    rows=game.engine.run(state,(event(1,"pass"),))
    assert {o.state.inventory[0].building_type:o.probability for o in rows}=={B.PIGGY_BANK:Fraction(1,2),B.PIGLET_BANK:Fraction(1,2)}
    for o in rows:assert_fresh(o.state.inventory[0])
    state=replace(state,buildings=(BuildingInstance(1,B.CANNON,location=0),))
    row,=game.engine.run(state,(event(1,"pass"),))
    assert row.probability==1
    assert row.state.inventory[0].building_type==B.TREASURE
    assert_fresh(row.state.inventory[0])
    assert "cannon_reward_distribution" in game.registry.profile_assumptions_used


def test_rabbit_excludes_itself_and_uniformly_targets_eligible_placed_buildings():
    game,state=playable()
    state=replace(state,buildings=(BuildingInstance(1,B.RABBIT_INN,location=0),
                  BuildingInstance(2,B.SMALL_WALLET,location=1),BuildingInstance(3,B.WISHING_WELL,location=2),
                  BuildingInstance(4,B.PIGGY_BANK,location=3)),inventory=(BuildingInstance(5,B.SMALL_WALLET),))
    rows=game.engine.run(state,(event(1,"pass"),))
    assert len(rows)==2 and all(o.probability==Fraction(1,2) for o in rows)
    for row in rows:
        bonuses={b.instance_id:b.dice_coin_bonus for b in row.state.buildings+row.state.inventory}
        assert bonuses[1]==bonuses[4]==bonuses[5]==0
        assert bonuses[2]+bonuses[3]==1
    assert "random_target_distribution" in game.registry.profile_assumptions_used


@pytest.mark.parametrize("n", [2,3,4])
def test_uniform_target_n_targets(n):
    game,state=playable()
    state=replace(state,buildings=tuple(BuildingInstance(i,B.SMALL_WALLET,location=i) for i in range(n)),
                  stands=(StandInstance(20,S.MIMI),))
    rows=game.engine.run(state,(Event(E.ACTIVATE_STAND,20,payload=(("trigger","after"),)),))
    assert len(rows)==n and all(o.probability==Fraction(1,n) for o in rows)
    assert {next(b.instance_id for b in o.state.buildings if b.dice_coin_bonus==1) for o in rows}==set(range(n))


def test_empty_targets_still_need_separate_explicit_policy():
    game,state=playable()
    state=replace(state,buildings=(BuildingInstance(1,B.RABBIT_INN,location=0),))
    with pytest.raises(UnresolvedRule,match="empty_random_target"):game.engine.run(state,(event(1,"pass"),))
    game,state0=playable({"empty_random_target":"no_effect"})
    row,=game.engine.run(state,(event(1,"pass"),))
    assert row.state.wallet==state.wallet+6
    assert "random_target_distribution" not in game.registry.profile_assumptions_used


def test_fox_multi_target_is_uniform_without_replacement():
    game,state=playable({"fox_self_target":False})
    state=replace(state,buildings=(BuildingInstance(0,B.FOX_ANTIQUE_SHOP,level=2,location=0),)+
                  tuple(BuildingInstance(i,B.SMALL_WALLET,location=i) for i in range(1,4)))
    rows=game.engine.run(state,(event(0,"die",5),))
    assert len(rows)==3 and all(o.probability==Fraction(1,3) for o in rows)
    chosen={tuple(b.instance_id for b in o.state.buildings[1:] if b.xp) for o in rows}
    assert chosen==set(combinations(range(1,4),2))
    assert all(b.xp in {0,1} for o in rows for b in o.state.buildings)


def test_big_bag_uniform_placed_templates_not_full_copies():
    game,state=playable()
    state=replace(state,buildings=(BuildingInstance(1,B.TREASURE,level=3,xp=4,location=0,treasure_decay=7),
                  BuildingInstance(2,B.SMALL_WALLET,level=4,location=1,dice_coin_bonus=8,custom_counters=(("test",3),))),
                  stands=(StandInstance(20,S.BIG_BAG),),inventory=(BuildingInstance(4,B.PIGGY_BANK),),selected_packs=frozenset(Pack))
    rows=game.engine.run(state,(Event(E.ACTIVATE_STAND,20,payload=(("trigger","start"),)),))
    assert len(rows)==2 and all(o.probability==Fraction(1,2) for o in rows)
    assert {o.state.inventory[-1].building_type for o in rows}=={B.TREASURE,B.SMALL_WALLET}
    for row in rows:assert_fresh(row.state.inventory[-1])
    assert set(game.registry.profile_assumptions_used)=={"big_bag_distribution","big_bag_copy_state","big_bag_template"}


def test_stand_offers_are_uniform_subsets_and_eligible():
    game,state=playable()
    state=replace(state,selected_packs=frozenset({Pack.PIRATE}))
    pool={kind.value for kind in S if stand_eligible(kind,state.selected_packs,game.registry)}
    rows=configured_distribution(game.registry,"stand_offers",state)
    assert len(rows)==comb(len(pool),3)
    assert len({frozenset(o.state) for o in rows})==len(rows)
    assert all(len(o.state)==len(set(o.state))==3 and set(o.state)<=pool for o in rows)
    assert all(o.probability==Fraction(1,len(rows)) for o in rows)
    assert sum(o.probability for o in rows)==1


def test_small_stand_pool_offers_every_type():
    game,state=playable({"stand_offers":{"strategy":"uniform_eligible_stands","count":3,"types":["CREDIT_CARD","BIG_BAG"]}})
    row,=configured_distribution(game.registry,"stand_offers",state)
    assert row.probability==1 and set(row.state)=={"CREDIT_CARD","BIG_BAG"}


@pytest.mark.parametrize("packs", [frozenset({Pack.LUCK}),frozenset(Pack)])
def test_shop_slot_marginals_joint_mass_prices_templates_and_hybrids(packs):
    game,state=playable()
    state=replace(state,selected_packs=packs)
    rows=configured_distribution(game.registry,"shop_distribution",state)
    pool={kind for kind in B if eligible(kind,packs,game.registry)}
    assert len(rows)==len(pool)**3
    marginals=[defaultdict(Fraction) for _ in range(3)]
    for o in rows:
        assert o.probability==Fraction(1,len(pool)**3)
        for slot,offer in enumerate(o.state):
            kind=B(offer["building"]["building_type"])
            marginals[slot][kind]+=o.probability
            assert offer["price"]=={"GREEN":8,"BLUE":16,"PURPLE":30,"GOLD":50}[game.registry.require(f"{kind.value}.rarity")]
        # All combinations reuse these validated templates; inspect each type below.
    assert sum(o.probability for o in rows)==1
    assert all(dict(m)=={k:Fraction(1,len(pool)) for k in pool} for m in marginals)
    assert any(len({offer['building']['building_type'] for offer in o.state})==1 for o in rows)
    for offer in {o.state[0]['building']['building_type']:o.state[0] for o in rows}.values():
        assert_fresh(building_from_template(state,offer['building'],game.registry))
    if packs=={Pack.LUCK}:
        assert B.RUDDER not in pool and B.LUCKY_COLOR_GATE not in pool
    else:assert {B.RUDDER,B.LUCKY_COLOR_GATE}<=pool


@pytest.mark.parametrize("count,price", [(0,5),(1,10),(8,45),(9,50),(1000,50)])
def test_refresh_prices_have_no_finite_array_end(count,price):
    game,state=playable({"shop_distribution":[{"probability":"1","value":[]}]})
    state=replace(state,wallet=100,shop_refresh_count=count)
    row,=apply_action(game,state,Action("REFRESH_SHOP"))
    assert row.state.wallet==100-price and row.state.shop_refresh_count==count+1
    assert "refresh_prices" in game.registry.profile_assumptions_used


def test_strict_blocks_playable_runs_tracks_only_used_and_cache_repeats():
    data=load_file("examples/playable_defaults.json")
    strict,state=from_scenario(data,mode="strict")
    blocked=Expectimax(strict,horizon=1,management_depth=0,allowed_actions=data["allowed_actions"]).solve(state)
    assert blocked.exactness=="unresolved" and blocked.missing_rule_ids==("card_distribution",)
    game,state=from_scenario(data,profile="playable-defaults")
    solver=Expectimax(game,horizon=1,management_depth=0,allowed_actions=data["allowed_actions"])
    a,b=solver.solve(state),solver.solve(state)
    assert a==b and game.roll_cache_hits>0
    assert "assumption-based" in a.exactness and a.recommendations and not a.missing_rule_ids
    assert a.profile_assumptions_used==("card_distribution","generated_building_state")
    assert a.assumption_values["card_distribution"]["strategy"]=="uniform_eligible_buildings"
    assert "shop_distribution" not in a.assumptions_used
    a=rollout(game,state,iterations=30,seed=42,allowed_actions=data["allowed_actions"])
    b=rollout(game,state,iterations=30,seed=42,allowed_actions=data["allowed_actions"])
    assert a==b and "assumption-based" in a.exactness
    assert "card_distribution" in a.profile_assumptions_used
    data.update(profile="playable-defaults",rule_mode="playable")
    strict,_=from_scenario(data,mode="strict")
    assert strict.registry.profile is None
    with pytest.raises(UnresolvedRule):strict.registry.require("card_distribution")


def test_profile_does_not_promote_any_confidence_or_override_explicit_values():
    strict=RuleRegistry.builtin()
    playable=RuleRegistry.builtin(profile="playable-defaults")
    assert strict.values==playable.values
    assert playable.values["palunan_sale_scope"].confidence==C.UNKNOWN
    explicit=[{"probability":"1","value":template(B.SMALL_WALLET)}]
    registry=RuleRegistry.builtin({"card_distribution":explicit},profile="playable-defaults")
    _,state=game_fixture()
    row,=configured_distribution(registry,"card_distribution",state)
    assert row.probability==1 and not registry.profile_assumptions_used
    assert registry.assumptions_used==("card_distribution",)
    values=dict(strict.values)
    values['card_distribution']=RuleValue(explicit,C.VERIFIED_CURRENT,"Synthetic verified distribution for precedence regression only")
    registry=RuleRegistry(strict.version,values,profile="playable-defaults")
    configured_distribution(registry,"card_distribution",state)
    assert registry.exactness=="exact" and not registry.assumptions_used


def test_empirical_and_explicit_strategy_remain_exchangeable():
    game,state=playable()
    game.registry.empirical['card_distribution']={"method":"empirical","sample_count":10,"context":{},
       "distribution":[{"probability":"3/10","value":template(B.SMALL_WALLET)},
                       {"probability":"7/10","value":template(B.PIGGY_BANK)}]}
    rows=configured_distribution(game.registry,"card_distribution",state)
    assert [o.probability for o in rows]==[Fraction(3,10),Fraction(7,10)]
    assert not game.registry.profile_assumptions_used
    assert game.registry.exactness=="assumption-based"
    game,state=playable({"card_distribution":{"strategy":"explicit","outcomes":[{"probability":"1","value":template(B.SMALL_WALLET)}]}})
    row,=configured_distribution(game.registry,"card_distribution",state)
    assert row.state['building_type']==B.SMALL_WALLET and not game.registry.profile_assumptions_used


def test_shop_refresh_and_purchase_leave_slot_empty():
    # A configured small dynamic pool exercises real shop events without generating thousands of traces.
    game,state=playable({'shop_distribution':{'strategy':'uniform_eligible_buildings','slots':3,
                        'types':['SMALL_WALLET','PIGGY_BANK'],'template_rule':'generated_building_state','prices_rule':'purchase_prices'}})
    rows=game.engine.run(state,(Event(E.SHOP_REFRESH),))
    assert len(rows)==8 and all(o.probability==Fraction(1,8) for o in rows)
    for row in rows:
        assert len(row.state.shop_offers)==3
        for offer in row.state.shop_offers:assert_fresh(offer.building)
    current=rows[0].state
    bought,=apply_action(game,current,Action('BUY',target=1))
    assert [o.offer_id for o in bought.state.shop_offers]==[0,2]
    assert bought.state.wallet==current.wallet-8
    assert bought.state.stage_progress==current.stage_progress
    assert_fresh(bought.state.inventory[-1])
    assert 'shop_refill' in game.registry.profile_assumptions_used


def test_profile_used_before_budget_exhaustion_keeps_assumption_label():
    data=load_file('examples/playable_defaults.json')
    game,state=from_scenario(data,profile='playable-defaults')
    result=Expectimax(game,horizon=1,management_depth=0,node_budget=1,allowed_actions=data['allowed_actions']).solve(state)
    assert result.budget_exhausted and not result.missing_rule_ids
    assert result.exactness=='budget-exhausted / assumption-based'


def test_cache_restores_profile_provenance_after_empirical_roundtrip():
    data=load_file('examples/playable_defaults.json')
    game,state=from_scenario(data,profile='playable-defaults')
    solver=Expectimax(game,horizon=1,management_depth=0,allowed_actions=data['allowed_actions'])
    original=solver.solve(state)
    game.registry.empirical['card_distribution']={"method":"empirical","sample_count":1,"context":{},
        "distribution":[{"probability":"1","value":template(B.SMALL_WALLET)}]}
    empirical=solver.solve(state)
    assert empirical.empirical_rules_used==('card_distribution',)
    assert 'card_distribution' not in empirical.profile_assumptions_used
    game.registry.empirical.clear()
    restored=solver.solve(state)
    assert restored==original
    assert 'card_distribution' in restored.profile_assumptions_used
    assert 'assumption-based' in restored.exactness
