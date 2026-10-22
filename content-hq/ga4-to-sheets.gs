/**
 * Writes daily Google Analytics 4 numbers into a Google Sheet tab named "ga4_daily"
 * so Content HQ can read them. Free. Runs once a day after setup.
 *
 * Setup (about 15 minutes, once):
 * 1. Create a new Google Sheet. Extensions > Apps Script. Paste this file in.
 * 2. In Apps Script, click Services (+) and add "Google Analytics Data API".
 * 3. Set PROPERTY_ID below (GA4: Admin > Property settings > Property ID, digits only).
 * 4. Set WAITLIST_PATH and ARTICLE_PATH to match your site's URLs.
 * 5. Run updateGa4 once and approve the permissions. Then run installDailyTrigger once.
 * 6. Paste the Sheet's link into the Website card in Content HQ.
 *
 * This script has not been run against your account. If a step errors, send the error text.
 */
const PROPERTY_ID = 'PASTE_YOUR_GA4_PROPERTY_ID';
const WAITLIST_PATH = '/waitlist';   // any page whose path contains this counts as the waitlist page
const ARTICLE_PATH = '/blog';        // pages whose path starts with this count as articles
const DAYS = 60;

function updateGa4() {
  const range = [{ startDate: DAYS + 'daysAgo', endDate: 'today' }];
  const all = run_({ dateRanges: range, dimensions: [{ name: 'date' }],
    metrics: [{ name: 'sessions' }, { name: 'activeUsers' }, { name: 'screenPageViews' }] });
  const waitlist = run_({ dateRanges: range, dimensions: [{ name: 'date' }], metrics: [{ name: 'screenPageViews' }],
    dimensionFilter: { filter: { fieldName: 'pagePath', stringFilter: { matchType: 'CONTAINS', value: WAITLIST_PATH } } } });
  const articles = run_({ dateRanges: range, dimensions: [{ name: 'date' }], metrics: [{ name: 'screenPageViews' }],
    dimensionFilter: { filter: { fieldName: 'pagePath', stringFilter: { matchType: 'BEGINS_WITH', value: ARTICLE_PATH } } } });

  const byDate = {};
  (all.rows || []).forEach(function (r) {
    byDate[r.dimensionValues[0].value] = [r.metricValues[0].value, r.metricValues[1].value, r.metricValues[2].value, '0', '0'];
  });
  (waitlist.rows || []).forEach(function (r) { const d = r.dimensionValues[0].value; if (byDate[d]) byDate[d][3] = r.metricValues[0].value; });
  (articles.rows || []).forEach(function (r) { const d = r.dimensionValues[0].value; if (byDate[d]) byDate[d][4] = r.metricValues[0].value; });

  const out = [['date', 'sessions', 'activeUsers', 'pageviews', 'waitlistPageViews', 'articleViews']];
  Object.keys(byDate).sort().forEach(function (d) {
    out.push([d.slice(0, 4) + '-' + d.slice(4, 6) + '-' + d.slice(6, 8)].concat(byDate[d].map(Number)));
  });
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  const sheet = ss.getSheetByName('ga4_daily') || ss.insertSheet('ga4_daily');
  sheet.clearContents();
  sheet.getRange(1, 1, out.length, out[0].length).setValues(out);
}

function run_(request) {
  return AnalyticsData.Properties.runReport(request, 'properties/' + PROPERTY_ID);
}

function installDailyTrigger() {
  ScriptApp.newTrigger('updateGa4').timeBased().everyDays(1).atHour(6).create();
}
