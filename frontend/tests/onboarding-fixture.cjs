/* Explicit test data only; the application never imports this fixture. */
const assert = require('node:assert/strict');
module.exports = async function completeTestOnboarding(request, base) {
  const response = await request.post(base + '/api/v2/onboarding/couples', {
    data: {person_a: 'Alex', person_b: 'Sam'},
  });
  assert.equal(response.status(), 200);
  const couple = await response.json();
  for (const person of couple.members) {
    const path = `${base}/api/v2/onboarding/couples/${couple.couple_id}/members/${person.id}`;
    const headers = {'X-Member-Token': person.token};
    const values = [{name: person.name}, {values: ['culture', 'food', 'outdoors']},
      {values: []}, {min: 20, max: 120, unit: 'couple', flexible: false},
      {novelty: .7}, {days: [], travel_minutes: 60, dietary: [], accessibility: []}, {skip: true}];
    for (const [index, value] of values.entries()) {
      const saved = await request.put(path + '/answers', {
        headers, data: {step: index + 1, value, privacy_scope: 'COUPLE_RECOMMENDATION'},
      });
      assert.equal(saved.status(), 200);
    }
    const completed = await request.post(path + '/complete', {headers});
    assert.equal(completed.status(), 200);
  }
  return couple;
};
