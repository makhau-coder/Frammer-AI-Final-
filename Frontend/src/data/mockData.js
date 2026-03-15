export const clients = [
  { id: 'c1', name: 'MediaCorp Global' },
  { id: 'c2', name: 'Visionary Studios' },
  { id: 'c3', name: 'ContentWave' },
  { id: 'c4', name: 'DigitalPulse Media' },
  { id: 'c5', name: 'Apex Broadcasting' },
];

export const channels = [
  { id: 'ch1', name: 'News Daily', client_id: 'c1' },
  { id: 'ch2', name: 'Sports Live', client_id: 'c1' },
  { id: 'ch3', name: 'Entertainment Hub', client_id: 'c2' },
  { id: 'ch4', name: 'Tech Reviews', client_id: 'c2' },
  { id: 'ch5', name: 'Lifestyle Now', client_id: 'c3' },
  { id: 'ch6', name: 'Finance Today', client_id: 'c3' },
  { id: 'ch7', name: 'Travel Diaries', client_id: 'c4' },
  { id: 'ch8', name: 'Food Network', client_id: 'c4' },
  { id: 'ch9', name: 'Music Central', client_id: 'c5' },
  { id: 'ch10', name: 'Documentary Plus', client_id: 'c5' },
];

export const users = [
  { id: 'u1', name: 'Alice Chen', team: 'Editorial' },
  { id: 'u2', name: 'Bob Martinez', team: 'Editorial' },
  { id: 'u3', name: 'Carol Singh', team: 'Production' },
  { id: 'u4', name: 'David Kim', team: 'Production' },
  { id: 'u5', name: 'Eva Müller', team: 'Operations' },
  { id: 'u6', name: 'Frank Li', team: 'Operations' },
  { id: 'u7', name: 'Grace Obi', team: 'Editorial' },
  { id: 'u8', name: 'Hassan Ali', team: 'Production' },
  { id: 'u9', name: 'Iris Tanaka', team: 'Marketing' },
  { id: 'u10', name: 'Jake Wilson', team: 'Marketing' },
  { id: 'u11', name: 'Kira Patel', team: 'Editorial' },
  { id: 'u12', name: 'Leo Rossi', team: 'Production' },
  { id: 'u13', name: 'Maya Johnson', team: 'Operations' },
  { id: 'u14', name: 'Nils Berg', team: 'Marketing' },
  { id: 'u15', name: 'Olivia Park', team: 'Editorial' },
];

const languages = ['English', 'Hindi', 'Spanish', 'Arabic'];
const inputTypes = ['Interview', 'Podcast', 'Webinar', 'Conference', 'News Broadcast'];
const outputTypes = ['Reel', 'Short', 'Chapter', 'Summary', 'Viral Clip'];
const platforms = ['YouTube', 'Instagram', 'TikTok', 'Twitter/X', 'LinkedIn'];
const teams = ['Editorial', 'Production', 'Operations', 'Marketing'];

function randomItem(arr) {
  return arr[Math.floor(Math.random() * arr.length)];
}

function randomDate(start, end) {
  return new Date(start.getTime() + Math.random() * (end.getTime() - start.getTime()));
}

function generateVideos() {
  const videos = [];
  const startDate = new Date('2025-09-01');
  const endDate = new Date('2026-03-10');

  for (let i = 0; i < 100; i++) {
    const uploadDate = randomDate(startDate, endDate);
    const isProcessed = Math.random() > 0.08;
    const processedDate = isProcessed
      ? new Date(uploadDate.getTime() + Math.random() * 3600000 * 4)
      : null;
    const isPublished = isProcessed && Math.random() > 0.3;
    const publishedDate = isPublished && processedDate
      ? new Date(processedDate.getTime() + Math.random() * 3600000 * 12)
      : null;
    const channel = randomItem(channels);
    const user = randomItem(users);
    const platform = isPublished ? randomItem(platforms) : null;

    videos.push({
      video_id: `VID-${String(i + 1).padStart(4, '0')}`,
      headline: generateHeadline(i),
      source: `https://source.media/${String(i + 1).padStart(4, '0')}`,
      uploaded_at: uploadDate.toISOString(),
      processed_at: processedDate?.toISOString() || null,
      published_at: publishedDate?.toISOString() || null,
      published_flag: isPublished,
      client_id: channel.client_id,
      channel_id: channel.id,
      user_id: user.id,
      team_name: user.team,
      language: randomItem(languages),
      input_type: randomItem(inputTypes),
      output_type: randomItem(outputTypes),
      duration: Math.floor(30 + Math.random() * 3570),
      published_platform: platform,
      published_url: isPublished ? `https://${platform?.toLowerCase()}.com/v/${String(i + 1).padStart(4, '0')}` : null,
      billable_flag: isPublished && Math.random() > 0.15,
    });
  }

  return videos.sort((a, b) => new Date(a.uploaded_at).getTime() - new Date(b.uploaded_at).getTime());
}

function generateHeadline(index) {
  const headlines = [
    'Breaking: Market Rally Continues', 'Exclusive Interview with CEO',
    'Top 10 Tech Innovations 2026', 'Behind the Scenes Documentary',
    'Live Sports Highlights Recap', 'Travel Guide: Hidden Gems of Asia',
    'Cooking Masterclass: Italian Cuisine', 'Music Festival Live Coverage',
    'Finance Deep Dive: Crypto Trends', 'Lifestyle: Morning Routines',
    'Podcast Ep 45: Future of AI', 'Conference Keynote: Digital Media',
    'News Roundup: Weekly Digest', 'Interview: Rising Stars in Film',
    'Webinar: Content Strategy 2026', 'Sports Analysis: Season Preview',
    'Tech Review: Latest Smartphones', 'Documentary: Ocean Conservation',
    'Entertainment: Award Show Recap', 'Health & Wellness Tips',
  ];
  return headlines[index % headlines.length] + (index >= 20 ? ` #${index}` : '');
}

export const videos = generateVideos();

export const dimensions = {
  languages,
  inputTypes,
  outputTypes,
  platforms,
  teams,
};
