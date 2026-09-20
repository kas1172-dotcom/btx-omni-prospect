import { expect, test } from '@playwright/test'

test('late itinerary save preserves edits and added stops, then saves with the returned version', async ({ page }) => {
  let releaseSave
  const heldSave = new Promise(resolve => { releaseSave = resolve })
  let savedPlan = null
  const writes = []
  await page.route('**/api/itineraries/current', async route => {
    if (route.request().method() === 'GET') return route.fulfill({ json: { itinerary: savedPlan } })
    const body = route.request().postDataJSON()
    writes.push(body)
    savedPlan = { ...body, version: writes.length }
    const response = savedPlan
    if (writes.length === 1) await heldSave
    await route.fulfill({ json: response })
  })
  await page.goto('/#/map')
  const results = page.getByRole('region', { name: 'Map results', exact: true })
  const dialog = page.getByRole('dialog', { name: 'Itinerary', exact: true })
  const add = async name => {
    await results.getByRole('button').filter({ hasText: new RegExp(`^${name}`) }).first().click()
    await page.getByRole('complementary', { name: 'Selected map location', exact: true }).getByRole('button', { name: 'Add to itinerary', exact: true }).click()
  }
  await add('KLA')
  await expect(dialog).toContainText('1 selected')
  await dialog.getByRole('button', { name: 'Save itinerary', exact: true }).click()
  await expect.poll(() => writes.length).toBe(1)
  await dialog.getByLabel('Itinerary name', { exact: true }).fill('Updated while saving')
  await dialog.getByRole('button', { name: 'Close', exact: true }).click()
  await add('Boeing')
  releaseSave()
  await expect(dialog).toContainText('Version 1')
  await expect(dialog).toContainText('2 selected')
  await expect(dialog).toContainText('Pending changes')
  await expect(dialog.getByLabel('Itinerary name', { exact: true })).toHaveValue('Updated while saving')
  await dialog.getByRole('button', { name: 'Save itinerary', exact: true }).click()
  await expect(dialog).toContainText('Saved version 2')
  expect(writes[1].expected_version).toBe(1)
  expect(writes[1].stops).toHaveLength(2)
  expect(writes[1].title).toBe('Updated while saving')
  await page.reload()
  await page.getByRole('button', { name: 'Itinerary', exact: true }).click()
  await expect(dialog).toContainText('2 selected')
  await expect(dialog.getByLabel('Itinerary name', { exact: true })).toHaveValue('Updated while saving')
})
