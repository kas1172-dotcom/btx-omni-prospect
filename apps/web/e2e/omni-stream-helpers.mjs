export async function readOmniAnswer(response, page) {
  return (await readOmniResult(response, page)).response
}

export async function readOmniResult(response, page) {
  try {
    const block = (await response.text()).split('\n\n').find(part => part.startsWith('event: answer\n'))
    if (!block) throw new Error('Omni stream did not contain a completed answer')
    return JSON.parse(block.split('\ndata: ')[1])
  } catch (error) {
    // Chromium can evict completed SSE bodies from its debugging protocol. Read
    // the same persisted turn, never issue a second question or bypass ownership.
    if (!page || !String(error).includes('Network.getResponseBody')) throw error
    const question = response.request().postDataJSON().question
    const principalToken = response.request().headers()['x-btx-principal-token']
    const options = { headers: principalToken ? { 'X-BTX-Principal-Token': principalToken } : {} }
    for (let attempt = 0; attempt < 20; attempt++) {
      const threads = await (await page.request.get('/api/omni/conversations', options)).json()
      for (const item of threads.items.slice(0, 3)) {
        const thread = await (await page.request.get('/api/omni/conversations/' + item.id, options)).json()
        const turns = thread.turns ?? []
        if (turns.at(-2)?.text === question && turns.at(-1)?.response) return { response: turns.at(-1).response, conversation_id: item.id }
      }
      await new Promise(resolve => setTimeout(resolve, 100))
    }
    throw error
  }
}

export function streamAnswer(response) {
  return 'event: answer\ndata: ' + JSON.stringify({ response }) + '\n\nevent: done\ndata: {}\n\n'
}
