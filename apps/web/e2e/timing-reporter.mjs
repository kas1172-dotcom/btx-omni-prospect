export default class TimingReporter {
  onEnd(result) {
    const duration = result.duration ?? 0
    console.log(`E2E timing: ${result.status}; ${Math.round(duration / 1000)}s elapsed`)
  }
}
