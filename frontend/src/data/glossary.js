// Single source of truth for every financial term used in the UI.
// Keys are referenced by the <Term id="..."> component and by `term_id` in API responses.
export const glossary = {
  'principal': {
    title: 'Principal',
    plain: 'The original amount of money you borrow or invest, before any interest.',
  },
  'compound-interest': {
    title: 'Compound Interest',
    plain: 'Interest that earns more interest. Each period you earn interest on what you started with plus the interest you’ve already earned, so growth speeds up over time.',
  },
  'equity': {
    title: 'Equity',
    plain: 'The portion of an asset you actually own. For a home, it is the house’s value minus what you still owe on the loan.',
  },
  'term-deposit': {
    title: 'Term Deposit',
    plain: 'You lock money with a bank for a set time at a guaranteed interest rate. Predictable and low risk, but you can’t touch it without penalty until it matures.',
  },
  'index-fund': {
    title: 'Index Fund',
    plain: 'A low-fee fund that buys a wide slice of the share market (e.g. the global stock market). Volatile year-to-year, but historically a strong long-term grower.',
  },
  'emergency-fund': {
    title: 'Emergency Fund',
    plain: 'Cash kept liquid for life’s surprises (job loss, medical, car). The rule of thumb is 3–6 months of expenses, held in a high-yield savings account.',
  },
  'fixed-rate': {
    title: 'Fixed Rate',
    plain: 'An interest rate locked in for a set period (e.g. 1, 2, 3, or 5 years). Your payments don’t change during that window — useful for budgeting.',
  },
  'floating-rate': {
    title: 'Floating Rate (Variable)',
    plain: 'An interest rate that moves with the market. Cheaper if rates fall, more painful if they rise. Most flexible — you can usually pay off extra without break fees.',
  },
  'opportunity-cost': {
    title: 'Opportunity Cost',
    plain: 'What you give up by choosing one option over another. Fixing your mortgage long protects you if rates rise, but costs you if they fall — that gap is the opportunity cost.',
  },
  'amortization': {
    title: 'Amortization',
    plain: 'The way each loan payment is split between interest and reducing the principal. Early on, most of your payment is interest; near the end, most goes to principal.',
  },
  'ocr': {
    title: 'OCR (Official Cash Rate)',
    plain: 'The benchmark interest rate set by the Reserve Bank of New Zealand. Most other rates — mortgages, savings, term deposits — move in step with it.',
  },
  'inflation': {
    title: 'Inflation',
    plain: 'How fast prices rise over time. If your savings earn less than inflation, your money loses purchasing power even though the number gets bigger.',
  },
  'risk-profile': {
    title: 'Risk Profile',
    plain: 'How much short-term ups and downs you can tolerate. Low-risk favours guaranteed returns; high-risk accepts volatility for higher long-term growth.',
  },
  'horizon': {
    title: 'Time Horizon',
    plain: 'How long until you need the money. Longer horizons let you ride out market dips and lean into growth assets like index funds.',
  },
  'savings-rate': {
    title: 'Savings Rate',
    plain: 'The slice of your income you keep instead of spending — (income − expenses) ÷ income. The single most important number in long-term wealth-building.',
  },
  'auto-invest': {
    title: 'Auto-invest',
    plain: 'A scheduled transfer that buys investments for you on payday. Removes the “should I buy now?” decision and quietly builds wealth in the background.',
  },
  'kiwisaver': {
    title: 'KiwiSaver',
    plain: 'New Zealand’s opt-in retirement scheme. You contribute a percentage of your pay, your employer adds at least 3% if you contribute 3% or more, and the government chips in up to $521.43 a year via the Member Tax Credit — making it one of the highest-return savings vehicles available to most Kiwis.',
  },
  'employer-match': {
    title: 'Employer Match',
    plain: 'The percentage of your pay your employer adds to your KiwiSaver — minimum 3% in NZ, conditional on you contributing at least 3% yourself. Contributing less than the match leaves free money on the table.',
  },
  'pie-fund': {
    title: 'PIE (Portfolio Investment Entity)',
    plain: 'A New Zealand tax structure used by most KiwiSaver and managed funds. Returns are taxed at your PIR (capped at 28%), so high earners pay less than they would on equivalent bank interest.',
    aliases: ['PIE'],
  },
  'pir': {
    title: 'PIR (Prescribed Investor Rate)',
    plain: 'The tax rate applied to your PIE income — 10.5%, 17.5%, or 28%, set by your last two years of income. Picking the wrong PIR means wrong tax; most working adults default to 28%, with the IRD refunding overpayments at year end.',
  },
  'paye': {
    title: 'PAYE',
    plain: 'Pay As You Earn — the income tax your employer withholds from each paycheck. Your "take-home pay" is gross income net of PAYE plus the ACC earners\' levy.',
  },
  'debt-to-income': {
    title: 'Debt-to-income (DTI)',
    plain: 'Your total debt divided by your annual income. NZ banks apply DTI caps (around 6× for owner-occupiers) when sizing how much they\'ll lend.',
  },
  'mortgage-spread': {
    title: 'Mortgage Spread',
    plain: 'The gap between the OCR and the rate a bank actually charges you. It\'s how the bank makes its margin — widens when funding is tight, narrows when banks compete for business.',
    aliases: ['mortgage'],
  },
  'after-tax-return': {
    title: 'After-tax Return',
    plain: 'The return you actually keep after PIR or RWT. A 6% term deposit at 33% RWT is really 4.02% — that\'s the number that should beat inflation, not the headline rate.',
  },
  'financial-order-of-operations': {
    title: 'Financial Order of Operations',
    plain: 'A priority order most advisors use: (1) cover essentials, (2) capture free money (employer KiwiSaver match), (3) kill high-interest debt, (4) build the full emergency fund, (5) invest for the long term. Skipping ahead leaves return on the table.',
  },
  'high-interest-debt': {
    title: 'High-interest Debt',
    plain: 'Any debt charging materially more than you could safely earn investing — usually credit cards (18–24%) and personal loans (10%+). Always pay these off before investing — the guaranteed "return" from clearing them beats almost any market.',
  },
};

export function getTerm(id) {
  return glossary[id];
}

export const allTerms = Object.entries(glossary).map(([id, v]) => ({ id, ...v }));
