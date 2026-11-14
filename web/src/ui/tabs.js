import { cultivarsTab } from './tabs/cultivars.js';
import { modelTab } from './tabs/model.js';
import { scenariosTab } from './tabs/scenarios.js';
import { seasonTab } from './tabs/season.js';
import { siteTab } from './tabs/site.js';
import { windowTab } from './tabs/window.js';
import { yearsTab } from './tabs/years.js';

/** Tabs in display order: each has id, label, needsSite, optional async compute(ctx) and render(ctx, data, el). */
export const TABS = [seasonTab, yearsTab, windowTab, cultivarsTab, scenariosTab, siteTab, modelTab];
