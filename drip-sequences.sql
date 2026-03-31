-- ============================================================
-- TPL Collective - Brokerage-Specific Email Drip Sequences
-- 5 funnels x 7 steps each = 35 email steps
-- Execute against Supabase project: zyonidiybzrgklrmalbt
-- ============================================================

-- Funnel 1: KW Gut Punch (Full 7-Step)
INSERT INTO email_funnels (name, trigger_stage, description, active)
VALUES ('KW Gut Punch - 7 Step', 'new_kw_lead', 'Full 7-step sequence for Keller Williams agents frustrated with splits and cap', true);

INSERT INTO email_funnel_steps (funnel_id, step_order, subject, body, delay_days, active)
VALUES
(
  (SELECT id FROM email_funnels WHERE name = 'KW Gut Punch - 7 Step'),
  1,
  'The $27K question every KW agent should ask',
  'Hey [Name],

Quick question: do you know exactly how much you paid Keller Williams last year?

Not the split. Not the cap. The TOTAL number - split, royalties, franchise fees, tech fees, desk fees, E&O, transaction fees. All of it.

Most KW agents I talk to have never added it all up. When they do, the number is usually somewhere between $15K and $30K per year. Sometimes more.

At LPT Realty, the math is simple. $500 per transaction, capped at $5,000 per year. No franchise fee. No royalties. No desk fees.

That gap between what you pay now and $5K? That''s money you earned that you''re not keeping.

I built a calculator that does the math for you in 30 seconds:

https://tplcollective.ai/commission-calculator

Plug in your numbers. See what you''d keep.

- Joe DeSane
TPL Collective

[unsubscribe_link]',
  0,
  true
),
(
  (SELECT id FROM email_funnels WHERE name = 'KW Gut Punch - 7 Step'),
  2,
  'What your KW split actually costs you',
  'Hey [Name],

Let''s break down what Keller Williams actually takes from each deal.

The 70/30 split is just the start. On a $10,000 commission check, that''s $3,000 right off the top. Then add:

- 6% franchise fee (another $600)
- Technology fee ($100-200/month)
- Desk fee (varies by market center)
- Transaction fee ($75-150 per closing)
- E&O insurance

Now compare that to LPT: $500 flat. That''s it. No split, no franchise fee, no desk fee, no tech fee. Just $500 per deal, capped at $5K for the year.

On that same $10,000 check, you keep $9,500 at LPT instead of roughly $6,000 at KW.

Run your own numbers here:

https://tplcollective.ai/commission-calculator

The difference adds up fast.

- Joe

[unsubscribe_link]',
  2,
  true
),
(
  (SELECT id FROM email_funnels WHERE name = 'KW Gut Punch - 7 Step'),
  3,
  'Your commission calculator results',
  'Hey [Name],

Did you get a chance to run your numbers yet?

If not, takes 30 seconds:

https://tplcollective.ai/commission-calculator

If you did - I''m guessing the number was bigger than you expected. Most KW agents tell me they had no idea how much was being taken in total when you add up every fee.

The agents who switch to LPT typically keep $15K-$25K more per year. Some even more depending on production.

That''s not theoretical money. That''s actual dollars hitting your bank account instead of your brokerage''s.

Want me to walk through the numbers with you? 15 minutes, no pitch, just math:

https://calendly.com/discovertpl

Either way, the calculator is yours to keep. Share it with your team if you want.

- Joe

[unsubscribe_link]',
  5,
  true
),
(
  (SELECT id FROM email_funnels WHERE name = 'KW Gut Punch - 7 Step'),
  4,
  'Why KW agents are switching to LPT this year',
  'Hey [Name],

I talk to KW agents every week who are making the switch. The reasons are usually the same:

"I hit my cap and then had to keep paying royalties and fees."
"I was paying for training I never used."
"The profit share check never matched what they promised."

LPT Realty now has 21,000+ agents across the US. That growth didn''t come from advertising. It came from agents telling other agents about the math.

Here''s what most KW agents say after switching: they wish they''d done it sooner. Same clients, same closings, same way they run their business. The only difference is where the money goes.

Full comparison page here:

https://tplcollective.ai/vs/keller-williams

If you want to hear it straight from someone who spent 11 years at KW before switching, that''s me. Happy to talk:

https://calendly.com/discovertpl

- Joe

[unsubscribe_link]',
  8,
  true
),
(
  (SELECT id FROM email_funnels WHERE name = 'KW Gut Punch - 7 Step'),
  5,
  'KW Profit Share vs LPT HybridShare - honest comparison',
  'Hey [Name],

One thing that keeps KW agents from looking elsewhere is Profit Share. I get it - passive income sounds great.

But let''s be honest about how it actually works at KW:

- You need a massive downline to earn meaningful checks
- Market center profitability affects your payout
- Most agents earn very little from it

LPT Realty has HybridShare - their revenue sharing program. It''s structured differently. You earn a percentage based on the production of agents you sponsor, and it''s not tied to a single office''s profitability.

I''m not going to tell you one is definitively better than the other - that depends on your situation. But I will say this: many agents who thought Profit Share was keeping them at KW realized the math didn''t justify staying once they actually compared the numbers.

Worth a 15-minute conversation to compare both side by side:

https://calendly.com/discovertpl

I''ll show you my actual numbers. No pitch.

- Joe

[unsubscribe_link]',
  12,
  true
),
(
  (SELECT id FROM email_funnels WHERE name = 'KW Gut Punch - 7 Step'),
  6,
  'What switching from KW actually looks like',
  'Hey [Name],

The #1 fear I hear from KW agents: "Switching sounds like a huge hassle."

Here''s what it actually looks like:

1. You submit your transfer paperwork (takes 10 minutes)
2. Your license transfers in 3-5 business days
3. Your pending deals stay your deals
4. Your clients don''t notice anything different
5. You keep using whatever tools you already use

That''s it. No disruption. No downtime. No lost deals.

You keep your phone number, your email, your sphere, your marketing. The only thing that changes is the brokerage name on your license - and the amount hitting your bank account each month.

Most agents tell me the hardest part was deciding. The actual switch was the easy part.

If you want to talk through the process, I''m here:

https://calendly.com/discovertpl

- Joe

[unsubscribe_link]',
  17,
  true
),
(
  (SELECT id FROM email_funnels WHERE name = 'KW Gut Punch - 7 Step'),
  7,
  '15 minutes with Joe - no pitch, just math',
  'Hey [Name],

Last email in this series. I''m not going to keep filling your inbox.

Here''s the short version of everything I''ve shared:

- KW agents typically pay $15K-$30K/year in total brokerage costs
- LPT Realty caps at $5,000/year. Period.
- Switching takes 3-5 business days with zero disruption
- 21,000+ agents have already made the move

If the math makes sense for you, I''d love to spend 15 minutes walking through it together. No pitch, no pressure. Just your numbers on a screen.

https://calendly.com/discovertpl

If the timing isn''t right, no worries. The calculator is always there when you need it:

https://tplcollective.ai/commission-calculator

Either way - thanks for reading. I hope at least one of these emails made you think.

- Joe DeSane
TPL Collective

[unsubscribe_link]',
  21,
  true
);


-- Funnel 2: eXp Reality Check
INSERT INTO email_funnels (name, trigger_stage, description, active)
VALUES ('eXp Reality Check', 'new_exp_lead', 'Full 7-step sequence for eXp agents tired of complexity, Icon chasing, and hidden costs', true);

INSERT INTO email_funnel_steps (funnel_id, step_order, subject, body, delay_days, active)
VALUES
(
  (SELECT id FROM email_funnels WHERE name = 'eXp Reality Check'),
  1,
  'The eXp math nobody talks about',
  'Hey [Name],

eXp markets itself as a low-cost cloud brokerage. But have you added up what you actually pay?

Start with the 80/20 split. On a $10,000 commission, that''s $2,000 to eXp. Then there''s the $250 transaction fee, the $85/month cloud fee, and the $500/year ICON fee if you''re chasing that status.

Even after you cap at $16K, you''re still paying per-transaction fees.

At LPT Realty, it''s $500 per transaction, capped at $5,000 for the year. No split. No cloud fee. No monthly fees. No ICON tiers to chase.

Run the comparison yourself:

https://tplcollective.ai/commission-calculator

The numbers don''t lie.

- Joe DeSane
TPL Collective

[unsubscribe_link]',
  0,
  true
),
(
  (SELECT id FROM email_funnels WHERE name = 'eXp Reality Check'),
  2,
  'Icon status vs just keeping your money',
  'Hey [Name],

The ICON award at eXp is clever marketing. Hit your production goals, attract agents, close enough deals - and you get your cap back in stock.

But think about what you''re really doing: spending a year jumping through hoops to earn back money that LPT never would have taken in the first place.

At LPT, you cap at $5K. That''s it. No tiers. No production requirements to get your money back. No gamification. Just simple math.

The time and energy you spend chasing ICON status? Imagine putting that into growing your business or spending it with your family instead.

See the full comparison:

https://tplcollective.ai/vs/exp-realty

Worth thinking about.

- Joe

[unsubscribe_link]',
  2,
  true
),
(
  (SELECT id FROM email_funnels WHERE name = 'eXp Reality Check'),
  3,
  'eXp stock vs LPT stock - honest look',
  'Hey [Name],

One thing eXp does well: stock incentives. You can earn equity through production and recruiting.

LPT Realty also offers stock incentives. Agents can earn equity through their production and team building. Both companies are publicly traded.

I''m not going to tell you which stock program is better - I''m not a financial advisor and neither program is guaranteed.

What I WILL say: the stock shouldn''t be the reason you stay at a brokerage that costs you more per deal. Stock incentives are a bonus, not a substitute for keeping more of your commission today.

The question is simple: are you earning enough in eXp stock to justify paying $11K-$16K more per year in splits and fees vs LPT''s $5K cap?

Let''s do the math together:

https://calendly.com/discovertpl

No pitch. Just numbers side by side.

- Joe

[unsubscribe_link]',
  5,
  true
),
(
  (SELECT id FROM email_funnels WHERE name = 'eXp Reality Check'),
  4,
  'What eXp agents say after switching',
  'Hey [Name],

The most common thing I hear from agents who leave eXp:

"I didn''t realize how much the fees were adding up."

Between the split, the cloud fee, the transaction fees, and chasing ICON - many eXp agents are paying $12K-$18K per year in total brokerage costs. Some more.

At LPT, they cap at $5K and suddenly have an extra $7K-$13K per year. Same CRM options. Same transaction management. Same way they run their business.

The only thing that changed was their bottom line.

Full comparison page:

https://tplcollective.ai/vs/exp-realty

If you want to hear from someone who''s helped dozens of eXp agents make the switch:

https://calendly.com/discovertpl

- Joe

[unsubscribe_link]',
  8,
  true
),
(
  (SELECT id FROM email_funnels WHERE name = 'eXp Reality Check'),
  5,
  'Cloud brokerage doesn''t mean cheap brokerage',
  'Hey [Name],

eXp''s big pitch: "We''re a cloud brokerage so we pass the savings to you."

But the savings don''t seem to make it to the agent. No brick and mortar office, yet you''re still paying an 80/20 split, monthly cloud fees, and transaction fees that add up to $12K-$18K per year.

LPT Realty is also cloud-based. No physical offices. But they actually DO pass the savings along - $500 per deal, $5K annual cap.

The question isn''t "cloud vs traditional." The question is: where does the money go?

At eXp, it goes to splits and fees. At LPT, it stays in your pocket.

Run your numbers:

https://tplcollective.ai/commission-calculator

- Joe

[unsubscribe_link]',
  12,
  true
),
(
  (SELECT id FROM email_funnels WHERE name = 'eXp Reality Check'),
  6,
  'The 15-minute switch',
  'Hey [Name],

Worried switching from eXp will be complicated? It''s not.

Here''s the process:
1. Submit transfer paperwork (10 minutes)
2. License transfers in 3-5 business days
3. Pending deals stay yours
4. Your clients won''t notice a thing

No disruption. No lost momentum. Your CRM, your leads, your marketing - all yours.

The only thing that changes is you stop paying 80/20 and start keeping 100% (minus $500 per deal).

Most agents tell me they spent more time deliberating than actually switching.

Want to talk through the details?

https://calendly.com/discovertpl

15 minutes. I''ll answer every question you have.

- Joe

[unsubscribe_link]',
  17,
  true
),
(
  (SELECT id FROM email_funnels WHERE name = 'eXp Reality Check'),
  7,
  'Quick call? No pitch - just numbers',
  'Hey [Name],

This is my last email in this series.

The summary: eXp costs most agents $12K-$18K/year in total fees. LPT caps at $5K. The difference is real money that compounds every year.

If you want to see your specific numbers, I''ll walk through it with you. 15 minutes, a shared screen, and your actual production data. That''s it.

https://calendly.com/discovertpl

If the timing isn''t right, the calculator is always available:

https://tplcollective.ai/commission-calculator

Thanks for reading, [Name]. I hope it at least made you question the status quo.

- Joe DeSane
TPL Collective

[unsubscribe_link]',
  21,
  true
);


-- Funnel 3: RE/MAX Wake Up
INSERT INTO email_funnels (name, trigger_stage, description, active)
VALUES ('RE/MAX Wake Up', 'new_remax_lead', 'Full 7-step sequence for RE/MAX agents paying franchise fees, desk fees, and monthly overhead', true);

INSERT INTO email_funnel_steps (funnel_id, step_order, subject, body, delay_days, active)
VALUES
(
  (SELECT id FROM email_funnels WHERE name = 'RE/MAX Wake Up'),
  1,
  'How much does that RE/MAX sign really cost you?',
  'Hey [Name],

RE/MAX agents love to say "I keep 95% of my commission." And technically, that''s true at some offices.

But that 95% doesn''t include the franchise fee, the desk fee, the monthly office fee, the tech fee, the advertising fund contribution, or the transaction fees.

When you add all of it up, most RE/MAX agents are paying $12K-$20K+ per year in total brokerage costs.

At LPT Realty, it''s $500 per transaction, capped at $5,000 per year. No desk fee. No franchise fee. No monthly office fee.

$5K total. That''s the ceiling, not the starting point.

See your actual numbers:

https://tplcollective.ai/commission-calculator

Plug in your production. See the difference.

- Joe DeSane
TPL Collective

[unsubscribe_link]',
  0,
  true
),
(
  (SELECT id FROM email_funnels WHERE name = 'RE/MAX Wake Up'),
  2,
  'Franchise fees, desk fees, tech fees - add it up',
  'Hey [Name],

Let''s itemize what a typical RE/MAX agent pays annually:

- Desk fee: $500-$2,000/month ($6K-$24K/year)
- Franchise fee: varies by office
- Technology fee: $100-200/month
- Transaction fee: $150-$300 per closing
- E&O insurance: $500-$1,000/year
- Advertising/marketing fund: varies

Even at a "generous" 95/5 split, the fees pile on top.

Now here''s LPT:
- $500 per transaction
- $5,000 annual cap
- Zero desk fees, franchise fees, or monthly charges

That''s it. The entire list.

Most RE/MAX agents who run the comparison realize they''re paying 3x-4x what they would at LPT.

Run your own numbers:

https://tplcollective.ai/commission-calculator

It only takes 30 seconds.

- Joe

[unsubscribe_link]',
  2,
  true
),
(
  (SELECT id FROM email_funnels WHERE name = 'RE/MAX Wake Up'),
  3,
  'What if you kept 100% of your commission?',
  'Hey [Name],

Imagine closing a $12,000 commission deal and keeping $11,500 of it.

That''s how LPT Realty works. 100% commission, minus $500 per deal. Once you hit $5K in fees for the year, you keep everything after that. 100%. Zero fees.

No split. No royalty. No desk fee. No franchise fee.

RE/MAX made the high-split model famous. But "high split" still means splitting. At LPT, there''s no split at all.

The tools are comparable. The support is there. The difference is purely financial - and it''s significant.

See the full fee breakdown:

https://tplcollective.ai/fee-plans

Want to talk through how it works?

https://calendly.com/discovertpl

- Joe

[unsubscribe_link]',
  5,
  true
),
(
  (SELECT id FROM email_funnels WHERE name = 'RE/MAX Wake Up'),
  4,
  'RE/MAX agents who made the switch',
  'Hey [Name],

When RE/MAX agents switch to LPT, the reaction is usually the same:

"Why didn''t I do this sooner?"

They keep the same clients, the same systems, the same way they run their business. The only thing that changes is they stop writing big checks to their brokerage every month.

No more desk fee rent. No more franchise fees eating into their business. Just a simple, flat fee structure that makes sense.

LPT now has 21,000+ agents nationwide. A lot of them came from RE/MAX offices where the overhead was crushing their margins.

Full breakdown of the comparison:

https://tplcollective.ai/vs/remax

If you want to hear more about what the switch looks like in practice:

https://calendly.com/discovertpl

- Joe

[unsubscribe_link]',
  8,
  true
),
(
  (SELECT id FROM email_funnels WHERE name = 'RE/MAX Wake Up'),
  5,
  'Brand recognition vs your bank account',
  'Hey [Name],

I hear this a lot: "But RE/MAX is a recognized brand. Clients trust it."

Here''s the truth: your clients chose YOU. They didn''t Google "RE/MAX agent near me" and randomly pick your name. They came from your sphere, your marketing, your reputation.

The brand on your card isn''t closing your deals. You are.

So the question becomes: is that brand worth $10K-$20K per year in fees?

At LPT, you get tools, support, and technology. You still have a brokerage backing you. But you keep the money you earn.

Your personal brand is what matters. Not the logo on your sign.

Worth thinking about:

https://tplcollective.ai/lpt-explained

- Joe

[unsubscribe_link]',
  12,
  true
),
(
  (SELECT id FROM email_funnels WHERE name = 'RE/MAX Wake Up'),
  6,
  'Switching takes 3-5 business days',
  'Hey [Name],

If you''ve been thinking about making a move but dreading the process, here''s the good news: it''s simple.

1. Submit your transfer paperwork (10 minutes)
2. License transfers in 3-5 business days
3. Pending deals stay yours - no disruption
4. Your clients don''t know the difference

No franchise transfer fee. No complicated exit process. No gap in your ability to write offers.

The desk fee stops. The franchise fee stops. And your next commission check looks different.

Want to walk through the details?

https://calendly.com/discovertpl

I''ll answer every question in 15 minutes.

- Joe

[unsubscribe_link]',
  17,
  true
),
(
  (SELECT id FROM email_funnels WHERE name = 'RE/MAX Wake Up'),
  7,
  'Let''s run the numbers together',
  'Hey [Name],

Last email from me on this.

The summary: RE/MAX agents typically pay $12K-$20K+ per year between splits, desk fees, franchise fees, and everything else. LPT caps everything at $5K.

That''s potentially $7K-$15K more in your pocket every year. Over 5 years, that''s $35K-$75K.

If you want to see your exact numbers, let''s spend 15 minutes together. I''ll pull up the calculator, plug in your production, and show you the side-by-side.

https://calendly.com/discovertpl

No pitch. No pressure. Just math.

If the numbers don''t work for you, I''ll tell you that too. But they usually do.

- Joe DeSane
TPL Collective

[unsubscribe_link]',
  21,
  true
);


-- Funnel 4: Legacy Brokerage Escape (Coldwell Banker / Century 21)
INSERT INTO email_funnels (name, trigger_stage, description, active)
VALUES ('Legacy Brokerage Escape', 'new_legacy_lead', 'Full 7-step sequence for Coldwell Banker and Century 21 agents stuck with corporate overhead', true);

INSERT INTO email_funnel_steps (funnel_id, step_order, subject, body, delay_days, active)
VALUES
(
  (SELECT id FROM email_funnels WHERE name = 'Legacy Brokerage Escape'),
  1,
  'The hidden cost of a "big name" brokerage',
  'Hey [Name],

Working at a big-name brokerage sounds good on paper. Coldwell Banker. Century 21. The brand, the reputation, the training.

But here''s what they don''t put in the recruiting presentation: how much of YOUR money pays for all of that.

Corporate overhead, franchise fees, office leases, national advertising, tech platforms you may not even use. All of it gets passed down to you through splits, fees, and monthly charges.

Most agents at traditional brokerages pay $15K-$25K+ per year in total costs. Many don''t realize it because the fees are spread across so many line items.

At LPT Realty, the total cost is $500 per deal, capped at $5,000 per year.

See how much you could keep:

https://tplcollective.ai/commission-calculator

- Joe DeSane
TPL Collective

[unsubscribe_link]',
  0,
  true
),
(
  (SELECT id FROM email_funnels WHERE name = 'Legacy Brokerage Escape'),
  2,
  'Your split is just the beginning',
  'Hey [Name],

You probably know your commission split. But do you know your actual total cost?

At most traditional brokerages, the split is just layer one. On top of that:

- Franchise/royalty fees (3-8% of GCI)
- Office/desk fees ($300-$2,000/month)
- Technology fees ($100-300/month)
- Transaction coordination fees ($200-400/deal)
- Marketing fund contributions
- E&O insurance

When you stack all of these, a "70/30 split" can effectively become 50/50 or worse.

At LPT Realty, there''s one cost: $500 per deal, $5K annual cap. No split. No layers. No surprises on your commission statement.

Run the comparison:

https://tplcollective.ai/commission-calculator

The difference might surprise you.

- Joe

[unsubscribe_link]',
  2,
  true
),
(
  (SELECT id FROM email_funnels WHERE name = 'Legacy Brokerage Escape'),
  3,
  'Modern agents need modern tools',
  'Hey [Name],

Here''s what today''s top-producing agents actually use: AI-powered tools, content engines, social media automation, and data-driven lead scoring.

At TPL Collective, we give agents access to Dezzy.ai (LPT''s AI assistant), a content creation engine, social media tools, and an AI-powered CRM that helps you prioritize who to call and what to say.

These aren''t future promises. They''re live tools that agents use every day.

The traditional brokerage model was built for a different era. Desk fees made sense when you needed an office. Franchise fees made sense when brand recognition drove business. That''s not how real estate works anymore.

Your phone, your database, and your digital presence are your business now.

See what modern brokerage tools look like:

https://tplcollective.ai/lpt-explained

- Joe

[unsubscribe_link]',
  5,
  true
),
(
  (SELECT id FROM email_funnels WHERE name = 'Legacy Brokerage Escape'),
  4,
  'Agents who left traditional brokerages',
  'Hey [Name],

The agents who switch from traditional brokerages to LPT all say some version of the same thing:

"I was paying for a name, not a service."

They realized the leads came from their own work. The closings came from their own relationships. The brand on the sign didn''t generate their business - they did.

So they stopped paying for the brand and started keeping their money.

LPT Realty has 21,000+ agents now. A huge chunk came from traditional brokerages where the overhead didn''t match the value.

Same MLS access. Same ability to close deals. Same clients. Just more money in their pocket at the end of each month.

Want to hear more?

https://calendly.com/discovertpl

15 minutes. No pitch. Just an honest conversation.

- Joe

[unsubscribe_link]',
  8,
  true
),
(
  (SELECT id FROM email_funnels WHERE name = 'Legacy Brokerage Escape'),
  5,
  'What does your brokerage actually do for you?',
  'Hey [Name],

Honest question: what do you get for the $15K-$25K you pay your brokerage every year?

- Leads? Most agents generate their own.
- Training? YouTube has better content for free.
- Technology? You probably use your own CRM anyway.
- Office space? When''s the last time you actually went in?

The traditional brokerage model charges premium prices for services most agents don''t use or need anymore.

At LPT, you get broker support, compliance, technology tools, and a revenue share program. For $5K per year max.

The question isn''t "can you make the switch." It''s "can you afford not to."

See the full fee comparison:

https://tplcollective.ai/fee-plans

- Joe

[unsubscribe_link]',
  12,
  true
),
(
  (SELECT id FROM email_funnels WHERE name = 'Legacy Brokerage Escape'),
  6,
  'No franchise transfer fee, no complicated paperwork',
  'Hey [Name],

One thing that keeps agents at traditional brokerages: the fear that leaving will be complicated.

It''s not.

Here''s the actual process:
1. Notify your current brokerage
2. Submit transfer paperwork (10 minutes)
3. License transfers in 3-5 business days
4. Your pending deals stay your deals
5. You''re up and running at LPT

No franchise transfer fee. No "exit interview." No waiting period. Your clients won''t even notice the change.

The hardest part is making the decision. Everything after that is straightforward.

Questions? Let''s talk:

https://calendly.com/discovertpl

- Joe

[unsubscribe_link]',
  17,
  true
),
(
  (SELECT id FROM email_funnels WHERE name = 'Legacy Brokerage Escape'),
  7,
  '15 minutes to see if it makes sense',
  'Hey [Name],

This is my last email in this series. I don''t believe in spamming people.

Here''s what I know: agents at traditional brokerages pay significantly more than they need to. The brand name, the office, the corporate structure - it costs money, and that cost gets passed to you.

LPT Realty offers a simple alternative: 100% commission, $500 per deal, $5K annual cap. Plus revenue sharing, stock incentives, and modern AI tools.

If you want to spend 15 minutes looking at the numbers side by side, I''m here:

https://calendly.com/discovertpl

If the timing isn''t right, no worries. Bookmark the calculator for when you are ready:

https://tplcollective.ai/commission-calculator

Thanks for reading, [Name].

- Joe DeSane
TPL Collective

[unsubscribe_link]',
  21,
  true
);


-- Funnel 5: The Numbers Don't Lie (General)
INSERT INTO email_funnels (name, trigger_stage, description, active)
VALUES ('The Numbers Don''t Lie', 'new_general_lead', 'General 7-step sequence for agents from any brokerage or independent agents', true);

INSERT INTO email_funnel_steps (funnel_id, step_order, subject, body, delay_days, active)
VALUES
(
  (SELECT id FROM email_funnels WHERE name = 'The Numbers Don''t Lie'),
  1,
  'What if your brokerage worked for you?',
  'Hey [Name],

Quick thought experiment: what if your brokerage actually worked for you instead of the other way around?

No splits eating into your checks. No surprise fees on your commission statement. No monthly desk rent for an office you barely use.

That''s how LPT Realty works. 100% commission. $500 per transaction. Capped at $5,000 per year. After that, you keep everything.

It sounds too simple to be real. But 21,000+ agents are already doing it. LPT is one of the fastest-growing brokerages in the country for a reason.

See how much you''d save:

https://tplcollective.ai/commission-calculator

Takes 30 seconds. Might change your year.

- Joe DeSane
TPL Collective

[unsubscribe_link]',
  0,
  true
),
(
  (SELECT id FROM email_funnels WHERE name = 'The Numbers Don''t Lie'),
  2,
  'The real cost of staying where you are',
  'Hey [Name],

Most agents don''t think of their brokerage fees as an "expense." It''s just how things work, right?

But here''s a different way to look at it: every dollar your brokerage takes is a dollar you could invest in your business, save for retirement, or take home to your family.

If you''re paying $15K-$25K per year in total brokerage costs (and most agents are), that''s $75K-$125K over 5 years. That''s a real number.

At LPT, the maximum you''d pay is $5K per year. Over 5 years, that''s $25K total.

The difference? $50K-$100K. That''s not a rounding error. That''s life-changing money.

Run your specific numbers:

https://tplcollective.ai/commission-calculator

- Joe

[unsubscribe_link]',
  2,
  true
),
(
  (SELECT id FROM email_funnels WHERE name = 'The Numbers Don''t Lie'),
  3,
  '100% commission isn''t a gimmick - here''s the math',
  'Hey [Name],

When people hear "100% commission," they think there''s a catch. Fair enough - let me explain exactly how it works.

LPT Realty charges $500 per transaction. That''s the only cost per deal. Once your fees total $5,000 for the year (so 10 transactions), you''re capped. Every deal after that is $0 to the brokerage.

No split. No royalty. No franchise fee. No desk fee. No monthly tech fee.

How does LPT make money? Volume. With 21,000+ agents each paying up to $5K, the model works. They don''t need to take 30% of your check.

It''s the same concept as Costco: low margin, high volume, better deal for everyone.

Full breakdown here:

https://tplcollective.ai/fee-plans

Questions? I''m an open book:

https://calendly.com/discovertpl

- Joe

[unsubscribe_link]',
  5,
  true
),
(
  (SELECT id FROM email_funnels WHERE name = 'The Numbers Don''t Lie'),
  4,
  '21,000+ agents chose LPT Realty - here''s why',
  'Hey [Name],

LPT Realty went from startup to 21,000+ agents in a few years. That kind of growth doesn''t happen by accident.

It happens when agents do the math.

The top reasons agents switch to LPT:

1. Keep more money per deal (100% commission, $5K cap)
2. Revenue sharing through HybridShare
3. Stock incentives in a publicly traded company
4. Modern technology and AI tools
5. No desk fees, no franchise fees, no monthly overhead

This isn''t a pitch. These are the actual reasons agents give when you ask them why they moved.

See the full picture:

https://tplcollective.ai/lpt-explained

If you want to hear it directly from someone who helps agents make the switch every week:

https://calendly.com/discovertpl

- Joe

[unsubscribe_link]',
  8,
  true
),
(
  (SELECT id FROM email_funnels WHERE name = 'The Numbers Don''t Lie'),
  5,
  'AI tools that actually help you close',
  'Hey [Name],

Most brokerages promise "cutting-edge technology." Usually that means a clunky CRM and some email templates from 2015.

At TPL Collective, we give agents access to tools that actually move the needle:

- Dezzy.ai: LPT''s AI assistant for market data, scripts, and client communication
- AI content engine: social posts, listing descriptions, and marketing materials generated in seconds
- Lead scoring: AI ranks your leads so you know who to call first
- Automated drip campaigns: stay in front of prospects without lifting a finger

These tools are built into the TPL Collective ecosystem. They''re not add-ons or upsells. They''re included.

The brokerage of the future isn''t the one with the biggest office. It''s the one with the best tools.

See what we''re building:

https://tplcollective.ai

- Joe

[unsubscribe_link]',
  12,
  true
),
(
  (SELECT id FROM email_funnels WHERE name = 'The Numbers Don''t Lie'),
  6,
  'Revenue share that builds real wealth',
  'Hey [Name],

Beyond keeping more of your commission, LPT Realty offers HybridShare - a revenue sharing program that lets you build passive income by helping other agents discover the platform.

When agents you sponsor close deals, you earn a percentage. It''s not MLM - it''s a business model that rewards you for growing the team.

Some agents treat it as a nice bonus. Others have built it into a serious income stream.

Combined with stock incentives in a publicly traded company, LPT gives you multiple ways to build wealth beyond your next closing.

I''m happy to walk through how it works and what it could look like for you:

https://calendly.com/discovertpl

Or read more here:

https://tplcollective.ai/revshare

- Joe

[unsubscribe_link]',
  17,
  true
),
(
  (SELECT id FROM email_funnels WHERE name = 'The Numbers Don''t Lie'),
  7,
  'Ready to see the numbers? 15 min with Joe',
  'Hey [Name],

Last email from me. Here''s the bottom line:

- 100% commission, $500/deal, $5K annual cap
- Revenue sharing through HybridShare
- Stock incentives in a public company
- AI tools and content engine included
- Switching takes 3-5 business days

If any of that sounds interesting, let''s spend 15 minutes together. I''ll pull up your numbers, show you the comparison, and answer any questions.

No pitch. No pressure. If it doesn''t make sense for you, I''ll tell you.

https://calendly.com/discovertpl

If now isn''t the right time, the calculator is always there:

https://tplcollective.ai/commission-calculator

Thanks for reading, [Name]. Hope to talk soon.

- Joe DeSane
TPL Collective

[unsubscribe_link]',
  21,
  true
);
