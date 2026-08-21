# AI Data-Center Stack Map — where the rent hides

Structural map of the buildout, top of funnel to live capacity, with the niche layers worth
hunting. **This is a research map, not a buy list.** Every company named below is a *starting
point to verify live* — confirm it still owns the choke point, re-pull its multiple vs. its
own history, re-check the market cap in USD, and re-test purity before it earns a row. Supply
structure is durable; valuations and lead times are not. Never carry a name straight from
here into output without live sourcing.

## Contents
1. The dependency chain (top to bottom)
2. Niche layers, by where they bind
3. Reading a "constraint confession"
4. Tier-hunting notes (finding the micro-cap)

---

## 1. The dependency chain (top to bottom)

```
Hyperscaler capex guide  (demand signal — read the latest each quarter)
  → Accelerators / GPUs / custom ASICs
    → HBM stacks            (memory bandwidth wall)
    → Advanced packaging    (CoWoS / SoIC / panel-level — co-locates logic + HBM)
      → ABF substrates      (the package's own substrate)
      → Silicon interposer / RDL
    → Optical interconnect  (transceivers, then CPO — scale-up/scale-out fabric)
  → The box / rack
    → Liquid cooling        (cold plates, CDUs, quick disconnects, manifolds)
      → Vapor chambers / TIMs (heat off the die into the loop)
    → Power delivery in-rack (busbars, VRMs, power-shelf / BBU)
  → Facility power & grid
    → Transformers, switchgear, medium-voltage gear
    → Backup (gensets, UPS), grid interconnect queue
  → Enabling materials & services that cut across everything
    → Specialty gases & wet chemicals, photoresist
    → Test / burn-in (sockets, load boards, ATE, system-level test)
    → Fiber & cabling
```

Each arrow is a potential choke point. The binding one moves over time: when GPUs were the
constraint the rent sat at the accelerator; as that eases it migrates to HBM, then packaging,
then power, then cooling. **Your job is to find the layer about to bind, not the one already
on every front page.**

## 2. Niche layers, by where they bind

For each: what it is, why it can bind, geographic + supplier concentration, and incumbents to
*verify* (not to recommend).

**HBM (high-bandwidth memory).** Stacked DRAM that feeds the accelerator; the bandwidth wall.
Concentrated in Korea (+ one US name). Verify: SK Hynix (KRX), Samsung (KRX), Micron (US).
Watch the layer below — TSV/stacking tools, and DRAM itself going on allocation.

**Advanced packaging (CoWoS / SoIC / panel-level).** Co-packages logic + HBM on an
interposer; historically *the* gating step for accelerator output. Heavily Taiwan. Verify:
TSMC (TWSE / NYSE ADR), plus OSATs (ASE, Amkor) and packaging-equipment / materials suppliers
one layer down.

**ABF substrates.** The build-up film substrate the package sits on; long qual times, few
qualified lines. Skews Japan / Taiwan / Austria. Verify: Ibiden (TSE), Shinko (TSE), Unimicron
(TWSE), AT&S (Vienna). Watch the ABF *film* itself (Ajinomoto, TSE) as the layer below.

**Optical interconnect → CPO.** Transceivers today, co-packaged optics next; the scale-up
fabric. Watch laser sources, optical engines, and the shift from pluggable to CPO. Verify:
transceiver makers (US/China), laser / photonics suppliers, and connector/ferrule names.

**Liquid cooling.** Cold plates, CDUs, manifolds — and the genuinely niche pieces: **quick
disconnects** (dripless couplings, very few qualified suppliers) and **manifolds**. Verify:
Vertiv (US, system), plus coupling specialists (e.g. CPC / Staubli-type vendors — confirm the
public wrapper, many are private or buried in a conglomerate).

**Vapor chambers / heat spreaders & TIMs.** Move heat off the die into the loop. Thermal
interface materials and high-performance vapor chambers are quietly tight. Skews Taiwan
(thermal modules) and specialty-materials names. Verify the thermal-module makers (TWSE) and
TIM material suppliers — often a small line inside a larger chemicals company (dilution risk).

**In-rack power.** Busbars, power shelves, BBUs, VRMs as rack power density climbs. Verify
power-shelf and busbar specialists; many are sub-lines of larger electricals (watch purity).

**Facility power & grid.** Transformers, medium-voltage switchgear, the interconnect-queue
constraint. Skews Europe. Verify: the big EU electricals and transformer/switchgear pure-plays
— lead times here are measured in *years*, which is the whole thesis.

**Specialty gases & wet chemicals.** Cut across every fab and packaging step; quiet, sticky,
oligopolistic. Verify industrial-gas majors and niche electronic-chemical / photoresist names
(Japan-heavy).

**Test / burn-in.** Sockets, load boards, ATE, and system-level test as parts get more
expensive to ship dead. Verify ATE makers and socket/interface specialists.

## 3. Reading a "constraint confession"

The richest signal on an earnings call is a manager naming *their own* bottleneck. "We could
ship more but we're **limited by [supplier X / substrate / a specific tool]**" points one
layer down to a cleaner, often smaller, often offshore name that captures the rent. Chase the
confession downward until you hit the layer with the fewest qualified suppliers and the
longest qual time — that's where pricing power and the rerate live. Tag these every time you
find one and follow the pointer before writing the theme up.

## 4. Tier-hunting notes (finding the micro-cap)

- The **~$100M** name is usually the purest exposure and the least covered — frequently a
  single-product offshore supplier (a coupling maker, one substrate line, one thermal-module
  shop). It's also where ticker/limit/liquidity frictions bite hardest; always state the
  access route.
- The **~$10B** name is liquid but usually *already consensus* — be brutal in "what's priced
  in." Liquidity is not edge.
- When the clean micro-cap is private (common in quick disconnects, optical engines), say so
  and name the closest public wrapper with its dilution noted, rather than forcing a bad fit
  or inventing a ticker.
