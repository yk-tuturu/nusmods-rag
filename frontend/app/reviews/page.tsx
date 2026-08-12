import AppShell from "@/components/layout/AppShell";
import Icon from "@/components/Icon";

const REVIEWS = [
  {
    term: "AY23/24 Semester 1",
    context: "Computer Science Major • Taken in Year 1",
    difficulty: 5,
    workload: 5,
    text: "This module is no joke. The problem sets (PSets) will consume your weekends. Start early, ideally the moment they are released. The TAs are generally very helpful during tutorials, so make sure to ask questions. While the workload is insane, the feeling of getting AC (Accepted) on Coursemology is unmatched.",
    helpful: 142,
  },
  {
    term: "AY22/23 Semester 2",
    context: "Information Systems Major • Taken in Year 2",
    difficulty: 4,
    workload: 5,
    text: "Prof Sethi is an amazing lecturer. He explains complex algorithms visually which really helps. The midterms were brutal, but the finals were slightly more manageable. Do not underestimate the time needed for debugging Java code.",
    helpful: 89,
  },
];

function ratingColor(score: number) {
  if (score >= 4.5) return "text-error";
  if (score >= 3.5) return "text-primary-container";
  return "text-success-green";
}

export default function ReviewsPage() {
  return (
    <AppShell sideNavActive="Module Search">
      <div className="grid grid-cols-1 md:grid-cols-12 gap-md">
        <div className="md:col-span-4 flex flex-col gap-sm">
          <div className="bg-surface-container-lowest border border-surface-variant rounded-xl p-sm">
            <div className="flex justify-between items-start mb-2">
              <h1 className="font-headline-lg text-headline-lg text-on-surface">CS2040S</h1>
              <Icon
                name="bookmark_border"
                className="text-on-surface-variant hover:text-primary cursor-pointer transition-colors"
              />
            </div>
            <h2 className="font-body-lg text-body-lg text-on-surface-variant mb-4">
              Data Structures and Algorithms
            </h2>
            <div className="flex gap-2 mb-4">
              <span className="bg-primary text-on-primary px-2 py-1 rounded font-label-sm text-label-sm font-mono">
                4 MCs
              </span>
              <span className="bg-secondary-container text-on-secondary-container px-2 py-1 rounded font-label-sm text-label-sm font-mono">
                Computing
              </span>
            </div>
            <div className="grid grid-cols-2 gap-4 pt-4 border-t border-surface-variant">
              <div>
                <p className="font-label-sm text-label-sm font-mono text-on-surface-variant mb-1">
                  Difficulty
                </p>
                <div className="flex items-center gap-1">
                  <span className="font-headline-sm text-headline-sm text-error">4.8</span>
                  <span className="font-body-sm text-body-sm text-on-surface-variant">/ 5</span>
                </div>
              </div>
              <div>
                <p className="font-label-sm text-label-sm font-mono text-on-surface-variant mb-1">
                  Workload
                </p>
                <div className="flex items-center gap-1">
                  <span className="font-headline-sm text-headline-sm text-error">4.9</span>
                  <span className="font-body-sm text-body-sm text-on-surface-variant">/ 5</span>
                </div>
              </div>
            </div>
          </div>

          <div className="bg-surface-container-lowest border border-surface-variant rounded-xl p-sm relative overflow-hidden">
            <div className="flex items-center gap-2 mb-3">
              <Icon name="auto_awesome" className="text-tertiary" />
              <h3 className="font-headline-sm text-headline-sm text-on-surface">AI Summary</h3>
            </div>
            <p className="font-body-sm text-body-sm text-on-surface mb-3 leading-relaxed">
              Generally considered a rite of passage for CS students. Extremely heavy workload
              with weekly problem sets that demand significant time. However, highly rewarding
              and fundamental for technical interviews.
            </p>
            <div className="flex flex-wrap gap-2">
              {["Challenging Psets", "Great Lecturers", "High Time Commitment"].map((tag) => (
                <span
                  key={tag}
                  className="border border-outline-variant text-on-surface-variant px-2 py-1 rounded-full font-label-sm text-label-sm font-mono"
                >
                  {tag}
                </span>
              ))}
            </div>
          </div>
        </div>

        <div className="md:col-span-8 flex flex-col gap-sm">
          <div className="flex justify-between items-center bg-surface-container-lowest border border-surface-variant rounded-xl p-sm">
            <div className="flex gap-4">
              <button className="font-label-md text-label-md font-mono text-primary border-b-2 border-primary pb-1">
                All Reviews
              </button>
              <button className="font-label-md text-label-md font-mono text-on-surface-variant hover:text-on-surface pb-1 transition-colors">
                Recent
              </button>
              <button className="font-label-md text-label-md font-mono text-on-surface-variant hover:text-on-surface pb-1 transition-colors">
                Top Rated
              </button>
            </div>
            <div className="flex items-center gap-2 text-on-surface-variant">
              <Icon name="filter_list" />
              <span className="font-label-md text-label-md font-mono">Filter</span>
            </div>
          </div>

          {REVIEWS.map((review) => (
            <div
              key={review.term}
              className="bg-surface-container-lowest border border-surface-variant rounded-xl p-md"
            >
              <div className="flex justify-between items-start mb-4">
                <div>
                  <h4 className="font-headline-sm text-headline-sm text-on-surface">
                    {review.term}
                  </h4>
                  <p className="font-body-sm text-body-sm text-on-surface-variant">
                    {review.context}
                  </p>
                </div>
                <div className="flex gap-2">
                  <div className="text-center">
                    <div className="font-label-sm text-label-sm font-mono text-on-surface-variant">
                      Diff
                    </div>
                    <div className={`font-body-md text-body-md ${ratingColor(review.difficulty)}`}>
                      {review.difficulty}/5
                    </div>
                  </div>
                  <div className="text-center">
                    <div className="font-label-sm text-label-sm font-mono text-on-surface-variant">
                      Work
                    </div>
                    <div className={`font-body-md text-body-md ${ratingColor(review.workload)}`}>
                      {review.workload}/5
                    </div>
                  </div>
                </div>
              </div>
              <p className="font-body-md text-body-md text-on-surface mb-4">{review.text}</p>
              <div className="flex items-center gap-4 border-t border-surface-variant pt-3 mt-2">
                <button className="flex items-center gap-1 text-on-surface-variant hover:text-primary transition-colors">
                  <Icon name="thumb_up" />
                  <span className="font-label-md text-label-md font-mono">
                    {review.helpful} Helpful
                  </span>
                </button>
                <button className="flex items-center gap-1 text-on-surface-variant hover:text-on-surface transition-colors">
                  <Icon name="share" />
                  <span className="font-label-md text-label-md font-mono">Share</span>
                </button>
              </div>
            </div>
          ))}

          <p className="font-body-sm text-body-sm text-on-surface-variant text-center py-sm">
            Sample data shown — live review aggregation coming soon.
          </p>
        </div>
      </div>
    </AppShell>
  );
}
