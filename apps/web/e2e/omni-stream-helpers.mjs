export async function readOmniAnswer(response) {
  const block = (await response.text()).split('\n\n').find(part => part.startsWith('event: answer\n'))
  if (!block) throw new Error('Omni stream did not contain a completed answer')
  return JSON.parse(block.split('\ndata: ')[1]).response
}

export function streamAnswer(response) {
  return 'event: answer\ndata: ' + JSON.stringify({ response }) + '\n\nevent: done\ndata: {}\n\n'
}
