import { test, expect } from '@playwright/test'
import { openRelationshipWorkspace } from './helpers.mjs'

const viewports = [{ width: 360, height: 800 }, { width: 390, height: 844 }, { width: 768, height: 1024 }, { width: 1440, height: 900 }, { width: 1920, height: 1080 }]

for (const viewport of viewports) {
  for (const scene of ['D1', 'D2', 'D3']) {
    test(`${scene} canonical commercial route and evidence at ${viewport.width}x${viewport.height}`, async ({ page }, testInfo) => {
      await page.setViewportSize(viewport)
      await page.emulateMedia({ reducedMotion: 'reduce' })
      const account = scene === 'D3' ? 'boeing' : 'kla'
      const component = scene === 'D1' ? 'C2-KLA-01' : scene === 'D2' ? 'C2-KLA-03' : 'C2-BOEING-01'
      const errors = []
      page.on('pageerror', error => errors.push(error.message))
      await page.goto(`/#/accounts/${account}`)
      const section = await openRelationshipWorkspace(page)
      if (scene !== 'D1') await section.getByRole('combobox', { name: 'Objective', exact: true }).selectOption('commercial_fit')
      await expect(section).toHaveAttribute('aria-busy', 'false')
      const response = page.waitForResponse(r => r.url().endsWith('/api/relationships/query') && r.request().postDataJSON()?.source_component_id === component)
      await section.getByRole('combobox', { name: 'Component scope', exact: true }).selectOption(component)
      let data = await (await response).json()
      if (scene === 'D1') {
        await section.getByRole('combobox', { name: 'Compare account', exact: true }).selectOption('spacex')
        await expect(section.getByRole('combobox', { name: 'Compared component', exact: true }).locator('option[value="C2-SPACEX-01"]')).toHaveCount(1)
        const fourResponse = page.waitForResponse(r => r.url().endsWith('/api/relationships/query') && r.request().postDataJSON()?.target_component_id === 'C2-SPACEX-01')
        await section.getByRole('combobox', { name: 'Compared component', exact: true }).selectOption('C2-SPACEX-01')
        const four = await (await fourResponse).json()
        expect(four.evaluated_routes.every(r => r.hop_count <= 4)).toBe(true)
        const sixResponse = page.waitForResponse(r => r.url().endsWith('/api/relationships/query') && r.request().postDataJSON()?.depth === 6)
        await section.getByRole('combobox', { name: 'Search depth', exact: true }).selectOption('6')
        data = await (await sixResponse).json()
        expect(data.searched_depth).toBe(6)
      }
      expect(data.rubric_version).toBe('BTX_RELATIONSHIP_POC_1')
      expect(data.search_complete).toBe(true)
      let route
      if (scene === 'D1') {
        route = data.evaluated_routes.find(r => r.hop_count === 5 && r.node_ids.includes('SAMPLE:business_unit:gen-el-mec'))
        expect(route).toBeTruthy()
        expect(route.component_context.map(c => c.id).sort()).toEqual(['C2-KLA-01', 'C2-SPACEX-01'])
      } else if (scene === 'D2') {
        route = data.evaluated_routes.find(r => r.hop_count === 3 && r.factors.bottleneck === 3)
        const shorter = data.evaluated_routes.find(r => r.hop_count === 2 && r.factors.bottleneck === 1)
        expect(route).toBeTruthy()
        expect(shorter).toBeTruthy()
        expect(Number(route.utility)).toBeGreaterThan(Number(shorter.utility))
      } else {
        route = data.evaluated_routes.find(r => r.constraints.some(c => c.reason.includes('146 units remain')))
        expect(route).toBeTruthy()
        expect(route.execution_status).toBe('BLOCKED')
        expect(route.next_action).toMatch(/recovery and feasibility/)
      }
      await section.getByText('All returned routes · ordered text equivalent', { exact: true }).click()
      await section.locator(`[data-route-id="${route.path_id}"]`).click()
      await expect(section.getByRole('heading', { name: `Selected route · ${route.hop_count} actual edges`, exact: true })).toBeVisible()
      await expect(section).toHaveAttribute('aria-busy', 'false')
      if (scene === 'D3') await expect(section.getByText(/146 units remain against/).first()).toBeVisible()
      await section.getByText('Why this route · factors and evidence', { exact: true }).click()
      await expect(section).toContainText(`Route strength ${Number(route.utility).toFixed(1)} out of 100; it is not a probability`)
      if (viewport.width < 760) await section.getByRole('button', { name: 'Explore network', exact: true }).click()
      await section.getByRole('button', { name: 'Fit selected route', exact: true }).click()
      await expect(section).toHaveAttribute('aria-busy', 'false')
      await expect(section.getByRole('group', { name: 'Canonical relationship network', exact: true })).toBeVisible()
      if (scene === 'D1' && viewport.width === 1440) {
        await page.getByRole('button', { name: 'Open Omni assistant' }).click()
        const omniResponse = page.waitForResponse(response => response.url().endsWith('/api/omni') && response.request().method() === 'POST')
        await page.locator('#omni-message').fill('Explain this selected relationship route.')
        await page.getByRole('button', { name: 'Send', exact: true }).click()
        const response = await omniResponse
        expect(response.status()).toBe(200)
        expect(response.request().postDataJSON().context.relationship_selection.path_id).toBe(route.path_id)
        await page.getByRole('button', { name: 'Close Omni', exact: true }).click()
      }
      const labels = await section.locator('.ranked-stage foreignObject button.active').evaluateAll(nodes => nodes.map(node => ({
        text: node.textContent, clipped: node.scrollHeight > node.clientHeight || node.scrollWidth > node.clientWidth,
      })))
      expect(labels).toHaveLength(route.node_ids.length)
      expect(labels.filter(node => node.clipped)).toEqual([])
      expect(await page.evaluate(() => document.documentElement.scrollWidth - innerWidth)).toBeLessThanOrEqual(1)
      expect(errors).toEqual([])
      await testInfo.attach('canonical-scene-manifest', { body: JSON.stringify({ scene, account, component, as_of: data.scope.as_of, graph_revision: data.eligible_graph_revision, commercial_as_of: data.commercial_as_of, route, measured_browser_scope: 'Local persisted API and actual SVG; not hosted, Maps, Gemini, performance or CSO usability validation' }, null, 2), contentType: 'application/json' })
      await section.screenshot({ path: testInfo.outputPath(`${scene}-${viewport.width}.png`) })
    })
  }
}

test('Omni waits for an in-flight selected relationship before answering', async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 900 })
  await page.goto('/#/accounts/kla')
  const section = await openRelationshipWorkspace(page)
  const componentResponse = page.waitForResponse(response => response.url().endsWith('/api/relationships/query') && response.request().postDataJSON()?.source_component_id === 'C2-KLA-01')
  await section.getByRole('combobox', { name: 'Component scope', exact: true }).selectOption('C2-KLA-01')
  await componentResponse
  const accountResponse = page.waitForResponse(response => response.url().endsWith('/api/relationships/query') && response.request().postDataJSON()?.target_account_id === 'spacex')
  await section.getByRole('combobox', { name: 'Compare account', exact: true }).selectOption('spacex')
  await accountResponse
  await expect(section.getByRole('combobox', { name: 'Compared component', exact: true }).locator('option[value="C2-SPACEX-01"]')).toHaveCount(1)
  await page.route('**/api/relationships/query', async route => {
    if (route.request().postDataJSON()?.target_component_id === 'C2-SPACEX-01') await new Promise(resolve => setTimeout(resolve, 750))
    await route.continue()
  })
  await section.getByRole('combobox', { name: 'Compared component', exact: true }).selectOption('C2-SPACEX-01')
  await page.getByRole('button', { name: 'Open Omni assistant' }).click()
  await page.locator('#omni-message').fill('Explain the selected relationship route between KLA and SpaceX.')
  const omniRequest = page.waitForRequest(request => request.url().endsWith('/api/omni') && request.method() === 'POST')
  await page.getByRole('button', { name: 'Send', exact: true }).click()
  const request = await omniRequest
  expect(request.postDataJSON().context.relationship_selection).toMatchObject({
    source_account_id: 'kla',
    target_component_id: 'C2-SPACEX-01',
  })
})
