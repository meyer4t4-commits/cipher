const pptxgen = require("pptxgenjs");

let pres = new pptxgen();
pres.layout = 'LAYOUT_16x9';
pres.author = 'Mark Meyer';
pres.title = 'Forge - Sovereign AI for Business';

// Color palette
const colors = {
  darkBg: "0A0E1A",      // Very dark navy
  cardBg: "1B3A5C",      // Deep navy
  accentBlue: "4C6EF5",  // Electric blue
  white: "FFFFFF",
  lightGray: "E0E0E0",
  mutedGray: "A0A0A0",
  accentGreen: "10B981"  // Accent green for highlights
};

const fonts = {
  title: "Calibri",
  body: "Calibri Light"
};

// ============================================
// SLIDE 1: Title Slide
// ============================================
let slide1 = pres.addSlide();
slide1.background = { color: colors.darkBg };

slide1.addText("FORGE", {
  x: 0.5, y: 1.8, w: 9, h: 0.8,
  fontSize: 72, bold: true, fontFace: fonts.title,
  color: colors.white, align: "center", margin: 0
});

slide1.addText("Your Business. Your AI. Your Advantage.", {
  x: 0.5, y: 2.7, w: 9, h: 0.5,
  fontSize: 28, fontFace: fonts.title,
  color: colors.accentBlue, align: "center", margin: 0
});

slide1.addText("Powered by Elysian Protocol", {
  x: 0.5, y: 3.5, w: 9, h: 0.4,
  fontSize: 16, fontFace: fonts.body,
  color: colors.mutedGray, align: "center", margin: 0
});

// Accent line
slide1.addShape(pres.shapes.RECTANGLE, {
  x: 3.5, y: 4.2, w: 3, h: 0.04,
  fill: { color: colors.accentBlue }, line: { type: "none" }
});

slide1.addText("Mark Meyer  |  elysianprotocol.io", {
  x: 0.5, y: 5.0, w: 9, h: 0.35,
  fontSize: 12, fontFace: fonts.body,
  color: colors.mutedGray, align: "center", margin: 0
});

// ============================================
// SLIDE 2: The Problem
// ============================================
let slide2 = pres.addSlide();
slide2.background = { color: colors.darkBg };

slide2.addText("The Problem", {
  x: 0.5, y: 0.4, w: 9, h: 0.5,
  fontSize: 44, bold: true, fontFace: fonts.title,
  color: colors.white, align: "left", margin: 0
});

// Problem statement boxes
const problems = [
  { title: "Generic AI Tools", text: "ChatGPT doesn't know your business, your customers, or your workflows" },
  { title: "Data Privacy Concerns", text: "Your business information fed to public AI providers" },
  { title: "Manual, Repetitive Work", text: "Teams spend hours on tasks that should be automated" },
  { title: "No Memory", text: "AI forgets context between sessions—you have to repeat yourself" }
];

let problemY = 1.3;
problems.forEach((problem, idx) => {
  // Background card
  slide2.addShape(pres.shapes.RECTANGLE, {
    x: 0.5, y: problemY, w: 4.2, h: 0.95,
    fill: { color: colors.cardBg }, line: { type: "none" }
  });

  // Accent left border
  slide2.addShape(pres.shapes.RECTANGLE, {
    x: 0.5, y: problemY, w: 0.08, h: 0.95,
    fill: { color: colors.accentBlue }, line: { type: "none" }
  });

  slide2.addText(problem.title, {
    x: 0.7, y: problemY + 0.08, w: 3.8, h: 0.3,
    fontSize: 14, bold: true, fontFace: fonts.title,
    color: colors.accentBlue, align: "left", margin: 0
  });

  slide2.addText(problem.text, {
    x: 0.7, y: problemY + 0.42, w: 3.8, h: 0.45,
    fontSize: 11, fontFace: fonts.body,
    color: colors.lightGray, align: "left", margin: 0
  });

  problemY += 1.05;
});

// ============================================
// SLIDE 3: The Solution
// ============================================
let slide3 = pres.addSlide();
slide3.background = { color: colors.darkBg };

slide3.addText("The Solution: Forge", {
  x: 0.5, y: 0.4, w: 9, h: 0.5,
  fontSize: 44, bold: true, fontFace: fonts.title,
  color: colors.white, align: "left", margin: 0
});

// Left side: description
slide3.addText([
  { text: "Your own AI intelligence", options: { breakLine: true, bold: true } },
  { text: "\n" },
  { text: "Customized for your business operations", options: { breakLine: true } },
  { text: "Remembers every interaction and decision", options: { breakLine: true } },
  { text: "Routes to the best model for each task", options: { breakLine: true } },
  { text: "Your data stays completely private", options: { breakLine: true } },
  { text: "Learns your business rules and workflows" }
], {
  x: 0.5, y: 1.3, w: 4.8, h: 3.2,
  fontSize: 16, fontFace: fonts.body,
  color: colors.lightGray, align: "left", valign: "top", margin: 0
});

// Right side: visual callout
slide3.addShape(pres.shapes.RECTANGLE, {
  x: 5.7, y: 1.3, w: 3.8, h: 1.4,
  fill: { color: colors.cardBg }, line: { type: "none" }
});

slide3.addText("Sovereign AI", {
  x: 5.9, y: 1.45, w: 3.4, h: 0.3,
  fontSize: 18, bold: true, fontFace: fonts.title,
  color: colors.accentBlue, align: "left", margin: 0
});

slide3.addText("Your business intelligence stays in your control. Persistent memory. Multi-model routing. Zero data sharing.", {
  x: 5.9, y: 1.85, w: 3.4, h: 0.8,
  fontSize: 12, fontFace: fonts.body,
  color: colors.lightGray, align: "left", margin: 0
});

// Stats section
slide3.addShape(pres.shapes.RECTANGLE, {
  x: 5.7, y: 3.0, w: 3.8, h: 1.5,
  fill: { color: colors.accentBlue }, line: { type: "none" }
});

slide3.addText("100%", {
  x: 5.9, y: 3.15, w: 1.7, h: 0.5,
  fontSize: 48, bold: true, fontFace: fonts.title,
  color: colors.darkBg, align: "center", margin: 0
});

slide3.addText("Data Privacy", {
  x: 5.9, y: 3.75, w: 1.7, h: 0.6,
  fontSize: 13, bold: true, fontFace: fonts.body,
  color: colors.darkBg, align: "center", margin: 0
});

slide3.addText("Your data. Never shared.", {
  x: 7.7, y: 3.15, w: 1.65, h: 1.2,
  fontSize: 12, fontFace: fonts.body,
  color: colors.darkBg, align: "center", valign: "middle", margin: 0
});

// ============================================
// SLIDE 4: How It Works
// ============================================
let slide4 = pres.addSlide();
slide4.background = { color: colors.darkBg };

slide4.addText("How It Works", {
  x: 0.5, y: 0.4, w: 9, h: 0.5,
  fontSize: 44, bold: true, fontFace: fonts.title,
  color: colors.white, align: "left", margin: 0
});

// Three step process
const steps = [
  { num: "1", title: "Connect", desc: "Link your business data, tools, and workflows" },
  { num: "2", title: "Configure", desc: "Define rules, playbooks, and AI behaviors" },
  { num: "3", title: "Command", desc: "Deploy Forge to automate and amplify your team" }
];

const stepX = [0.8, 3.6, 6.4];
steps.forEach((step, idx) => {
  // Circle number
  slide4.addShape(pres.shapes.OVAL, {
    x: stepX[idx], y: 1.3, w: 0.7, h: 0.7,
    fill: { color: colors.accentBlue }, line: { type: "none" }
  });

  slide4.addText(step.num, {
    x: stepX[idx], y: 1.3, w: 0.7, h: 0.7,
    fontSize: 36, bold: true, fontFace: fonts.title,
    color: colors.darkBg, align: "center", valign: "middle", margin: 0
  });

  // Title
  slide4.addText(step.title, {
    x: stepX[idx] - 0.15, y: 2.15, w: 1.0, h: 0.4,
    fontSize: 18, bold: true, fontFace: fonts.title,
    color: colors.white, align: "center", margin: 0
  });

  // Description
  slide4.addText(step.desc, {
    x: stepX[idx] - 0.3, y: 2.65, w: 1.6, h: 1.2,
    fontSize: 12, fontFace: fonts.body,
    color: colors.lightGray, align: "center", margin: 0
  });

  // Connector arrow (except last)
  if (idx < 2) {
    slide4.addShape(pres.shapes.LINE, {
      x: stepX[idx] + 1.2, y: 1.65, w: 0.6, h: 0,
      line: { color: colors.accentBlue, width: 2 }
    });
    slide4.addText("→", {
      x: stepX[idx] + 1.0, y: 1.5, w: 0.8, h: 0.3,
      fontSize: 24, color: colors.accentBlue, align: "center", margin: 0
    });
  }
});

// Bottom CTA box
slide4.addShape(pres.shapes.RECTANGLE, {
  x: 1.5, y: 4.3, w: 7, h: 1.0,
  fill: { color: colors.cardBg }, line: { type: "none" }
});

slide4.addText("It's that simple. Forge becomes an extension of your team in minutes.", {
  x: 1.7, y: 4.4, w: 6.6, h: 0.8,
  fontSize: 14, fontFace: fonts.body,
  color: colors.accentBlue, align: "center", valign: "middle", margin: 0
});

// ============================================
// SLIDE 5: The Technology - Orchid Engine
// ============================================
let slide5 = pres.addSlide();
slide5.background = { color: colors.darkBg };

slide5.addText("The Technology: Orchid", {
  x: 0.5, y: 0.4, w: 9, h: 0.5,
  fontSize: 44, bold: true, fontFace: fonts.title,
  color: colors.white, align: "left", margin: 0
});

// Orchid description
slide5.addText("Multi-Model AI Router Built for Performance", {
  x: 0.5, y: 1.1, w: 9, h: 0.35,
  fontSize: 16, fontFace: fonts.body,
  color: colors.accentBlue, align: "left", margin: 0
});

// Three model cards
const models = [
  { name: "Claude 3.5", specialty: "Strategic thinking, reasoning, complex decisions", color: colors.accentBlue },
  { name: "Llama 3", specialty: "Speed and efficiency, real-time responses", color: colors.accentGreen },
  { name: "DeepSeek", specialty: "Code generation, technical problem solving", color: colors.accentBlue }
];

let modelX = 0.5;
models.forEach((model, idx) => {
  slide5.addShape(pres.shapes.RECTANGLE, {
    x: modelX, y: 1.8, w: 2.9, h: 3.0,
    fill: { color: colors.cardBg }, line: { type: "none" }
  });

  // Top accent
  slide5.addShape(pres.shapes.RECTANGLE, {
    x: modelX, y: 1.8, w: 2.9, h: 0.08,
    fill: { color: model.color }, line: { type: "none" }
  });

  slide5.addText(model.name, {
    x: modelX + 0.2, y: 2.0, w: 2.5, h: 0.4,
    fontSize: 18, bold: true, fontFace: fonts.title,
    color: model.color, align: "left", margin: 0
  });

  slide5.addText(model.specialty, {
    x: modelX + 0.2, y: 2.6, w: 2.5, h: 2.0,
    fontSize: 12, fontFace: fonts.body,
    color: colors.lightGray, align: "left", valign: "top", margin: 0
  });

  modelX += 3.15;
});

// Key features
slide5.addText("Intelligent routing ensures every task reaches the perfect model—no wasted compute, no suboptimal results.", {
  x: 0.5, y: 5.0, w: 9, h: 0.5,
  fontSize: 13, fontFace: fonts.body,
  color: colors.mutedGray, align: "left", margin: 0
});

// ============================================
// SLIDE 6: Key Differentiators
// ============================================
let slide6 = pres.addSlide();
slide6.background = { color: colors.darkBg };

slide6.addText("Why Forge? The Cipher Advantage", {
  x: 0.5, y: 0.4, w: 9, h: 0.5,
  fontSize: 44, bold: true, fontFace: fonts.title,
  color: colors.white, align: "left", margin: 0
});

const differentiators = [
  {
    icon: "⚡",
    title: "Persistent Memory",
    desc: "Remembers every interaction, decision, and preference across all sessions"
  },
  {
    icon: "🔐",
    title: "Sovereign Data",
    desc: "Zero external data sharing. Your business intelligence stays completely private"
  },
  {
    icon: "🧠",
    title: "Business Customization",
    desc: "Learns your workflows, rules, and company playbooks automatically"
  },
  {
    icon: "⚙️",
    title: "Multi-Model Intelligence",
    desc: "Routes to Claude, Llama, or DeepSeek based on task requirements"
  },
  {
    icon: "🎯",
    title: "Purpose-Built for SMBs",
    desc: "Designed for roofing, construction, restaurants, accounting—vertical-specific"
  },
  {
    icon: "💰",
    title: "Premium Simplicity",
    desc: "$99-$499/mo. More intelligent. More private. More yours."
  }
];

let diffY = 1.2;
for (let i = 0; i < differentiators.length; i++) {
  const diff = differentiators[i];
  const isEven = i % 2 === 0;
  const xPos = isEven ? 0.5 : 5.2;

  if (i % 2 === 0 && i > 0) {
    diffY += 1.0;
  }

  // Card
  slide6.addShape(pres.shapes.RECTANGLE, {
    x: xPos, y: diffY, w: 4.3, h: 0.9,
    fill: { color: colors.cardBg }, line: { type: "none" }
  });

  // Icon emoji
  slide6.addText(diff.icon, {
    x: xPos + 0.15, y: diffY + 0.15, w: 0.5, h: 0.6,
    fontSize: 28, align: "center", margin: 0
  });

  // Title
  slide6.addText(diff.title, {
    x: xPos + 0.75, y: diffY + 0.1, w: 3.5, h: 0.3,
    fontSize: 13, bold: true, fontFace: fonts.title,
    color: colors.accentBlue, align: "left", margin: 0
  });

  // Description
  slide6.addText(diff.desc, {
    x: xPos + 0.75, y: diffY + 0.45, w: 3.5, h: 0.35,
    fontSize: 10, fontFace: fonts.body,
    color: colors.lightGray, align: "left", margin: 0
  });
}

// ============================================
// SLIDE 7: Use Cases
// ============================================
let slide7 = pres.addSlide();
slide7.background = { color: colors.darkBg };

slide7.addText("Built for Your Business", {
  x: 0.5, y: 0.4, w: 9, h: 0.5,
  fontSize: 44, bold: true, fontFace: fonts.title,
  color: colors.white, align: "left", margin: 0
});

const useCases = [
  {
    industry: "Roofing & Construction",
    examples: [
      "Estimate generation from photos & specs",
      "Customer follow-up automation",
      "Project scheduling and crew optimization"
    ]
  },
  {
    industry: "Restaurants & Hospitality",
    examples: [
      "Inventory forecasting and ordering",
      "Staff scheduling based on demand",
      "Customer feedback analysis & reviews"
    ]
  },
  {
    industry: "Accounting & Finance",
    examples: [
      "Invoice processing and categorization",
      "Tax compliance research automation",
      "Financial report generation"
    ]
  }
];

let useCaseY = 1.3;
useCases.forEach((useCase) => {
  // Background card
  slide7.addShape(pres.shapes.RECTANGLE, {
    x: 0.5, y: useCaseY, w: 9, h: 1.1,
    fill: { color: colors.cardBg }, line: { type: "none" }
  });

  // Accent left border
  slide7.addShape(pres.shapes.RECTANGLE, {
    x: 0.5, y: useCaseY, w: 0.08, h: 1.1,
    fill: { color: colors.accentBlue }, line: { type: "none" }
  });

  // Industry title
  slide7.addText(useCase.industry, {
    x: 0.75, y: useCaseY + 0.08, w: 8.7, h: 0.3,
    fontSize: 15, bold: true, fontFace: fonts.title,
    color: colors.accentBlue, align: "left", margin: 0
  });

  // Examples as bullets
  slide7.addText([
    { text: useCase.examples[0], options: { bullet: true, breakLine: true } },
    { text: useCase.examples[1], options: { bullet: true, breakLine: true } },
    { text: useCase.examples[2], options: { bullet: true } }
  ], {
    x: 0.95, y: useCaseY + 0.42, w: 8.5, h: 0.6,
    fontSize: 11, fontFace: fonts.body,
    color: colors.lightGray, align: "left", margin: 0
  });

  useCaseY += 1.25;
});

// ============================================
// SLIDE 8: Pilot Program
// ============================================
let slide8 = pres.addSlide();
slide8.background = { color: colors.darkBg };

slide8.addText("Join the Pilot", {
  x: 0.5, y: 0.4, w: 9, h: 0.5,
  fontSize: 44, bold: true, fontFace: fonts.title,
  color: colors.white, align: "left", margin: 0
});

// Main CTA box
slide8.addShape(pres.shapes.RECTANGLE, {
  x: 1.5, y: 1.3, w: 7, h: 1.5,
  fill: { color: colors.accentBlue }, line: { type: "none" }
});

slide8.addText("30-Day Free Pilot", {
  x: 1.7, y: 1.5, w: 6.6, h: 0.4,
  fontSize: 36, bold: true, fontFace: fonts.title,
  color: colors.darkBg, align: "center", margin: 0
});

slide8.addText("Full access to Forge and the Orchid engine. For early partners ready to build the future of AI-powered business.", {
  x: 1.7, y: 2.0, w: 6.6, h: 0.7,
  fontSize: 14, fontFace: fonts.body,
  color: colors.darkBg, align: "center", margin: 0
});

// What's included
slide8.addText("What's Included:", {
  x: 0.5, y: 3.1, w: 9, h: 0.3,
  fontSize: 16, bold: true, fontFace: fonts.title,
  color: colors.accentBlue, align: "left", margin: 0
});

const pilotItems = [
  "Unlimited Forge deployments for your team",
  "Direct support from the Elysian Protocol team",
  "Custom integration with your existing tools",
  "Onboarding and training for your workflows"
];

slide8.addText(pilotItems.map((item, idx) => ({
  text: item,
  options: { bullet: true, breakLine: idx < pilotItems.length - 1 }
})), {
  x: 0.8, y: 3.5, w: 8.4, h: 1.6,
  fontSize: 13, fontFace: fonts.body,
  color: colors.lightGray, align: "left", margin: 0
});

// ============================================
// SLIDE 9: Traction
// ============================================
let slide9 = pres.addSlide();
slide9.background = { color: colors.darkBg };

slide9.addText("Traction", {
  x: 0.5, y: 0.4, w: 9, h: 0.5,
  fontSize: 44, bold: true, fontFace: fonts.title,
  color: colors.white, align: "left", margin: 0
});

const tractionItems = [
  { metric: "Founder-Led", detail: "Solo founder building with deep technical expertise" },
  { metric: "Orchid Engine Live", detail: "Multi-model routing fully operational and tested" },
  { metric: "Integration Ready", detail: "Connectors for Zapier, Make, custom APIs" },
  { metric: "Customer Validation", detail: "Early conversations with roofing, construction, restaurant owners" }
];

let tY = 1.4;
tractionItems.forEach((item) => {
  // Metric box
  slide9.addShape(pres.shapes.RECTANGLE, {
    x: 0.5, y: tY, w: 4.3, h: 0.85,
    fill: { color: colors.cardBg }, line: { type: "none" }
  });

  slide9.addText(item.metric, {
    x: 0.7, y: tY + 0.08, w: 3.9, h: 0.3,
    fontSize: 15, bold: true, fontFace: fonts.title,
    color: colors.accentBlue, align: "left", margin: 0
  });

  slide9.addText(item.detail, {
    x: 0.7, y: tY + 0.43, w: 3.9, h: 0.35,
    fontSize: 11, fontFace: fonts.body,
    color: colors.lightGray, align: "left", margin: 0
  });

  // Accent dot
  slide9.addShape(pres.shapes.OVAL, {
    x: 9.0, y: tY + 0.32, w: 0.12, h: 0.12,
    fill: { color: colors.accentGreen }, line: { type: "none" }
  });

  tY += 1.0;
});

// Vision statement
slide9.addShape(pres.shapes.RECTANGLE, {
  x: 5.2, y: 1.4, w: 4.3, h: 3.4,
  fill: { color: colors.cardBg }, line: { type: "none" }
});

slide9.addText("The Vision", {
  x: 5.4, y: 1.6, w: 3.9, h: 0.3,
  fontSize: 16, bold: true, fontFace: fonts.title,
  color: colors.accentBlue, align: "left", margin: 0
});

slide9.addText("Every business should have its own AI intelligence. No giant corporations should own your business logic. No vendor lock-in. No data selling. Sovereign AI for the modern business.", {
  x: 5.4, y: 2.0, w: 3.9, h: 2.6,
  fontSize: 12, fontFace: fonts.body,
  color: colors.lightGray, align: "left", valign: "top", margin: 0
});

// ============================================
// SLIDE 10: Contact & CTA
// ============================================
let slide10 = pres.addSlide();
slide10.background = { color: colors.darkBg };

// Large accent background on right
slide10.addShape(pres.shapes.RECTANGLE, {
  x: 5.5, y: 0, w: 4.5, h: 5.625,
  fill: { color: colors.cardBg }, line: { type: "none" }
});

slide10.addText("Let's Build the Future", {
  x: 0.5, y: 1.2, w: 5, h: 0.6,
  fontSize: 44, bold: true, fontFace: fonts.title,
  color: colors.white, align: "left", margin: 0
});

slide10.addText("Sovereign AI for your business starts today.", {
  x: 0.5, y: 2.0, w: 5, h: 0.4,
  fontSize: 18, fontFace: fonts.body,
  color: colors.accentBlue, align: "left", margin: 0
});

// Contact info on right
slide10.addText("Mark Meyer", {
  x: 5.7, y: 1.3, w: 4.1, h: 0.4,
  fontSize: 28, bold: true, fontFace: fonts.title,
  color: colors.white, align: "left", margin: 0
});

slide10.addText("Founder, Elysian Protocol", {
  x: 5.7, y: 1.8, w: 4.1, h: 0.3,
  fontSize: 13, fontFace: fonts.body,
  color: colors.accentBlue, align: "left", margin: 0
});

// Contact details
const contactDetails = [
  { label: "Email", value: "mark@elysianprotocol.io" },
  { label: "Web", value: "elysianprotocol.io" },
  { label: "Twitter", value: "@markmeyeragi" }
];

let contactY = 2.4;
contactDetails.forEach((contact) => {
  slide10.addText(contact.label, {
    x: 5.7, y: contactY, w: 4.1, h: 0.2,
    fontSize: 10, fontFace: fonts.body,
    color: colors.mutedGray, align: "left", margin: 0
  });

  slide10.addText(contact.value, {
    x: 5.7, y: contactY + 0.25, w: 4.1, h: 0.3,
    fontSize: 12, bold: true, fontFace: fonts.body,
    color: colors.white, align: "left", margin: 0
  });

  contactY += 0.7;
});

// CTA button area
slide10.addShape(pres.shapes.RECTANGLE, {
  x: 5.7, y: 4.0, w: 4.1, h: 0.5,
  fill: { color: colors.accentBlue }, line: { type: "none" }
});

slide10.addText("Start Your Pilot Today", {
  x: 5.7, y: 4.0, w: 4.1, h: 0.5,
  fontSize: 14, bold: true, fontFace: fonts.title,
  color: colors.darkBg, align: "center", valign: "middle", margin: 0
});

// Write the presentation
pres.writeFile({ fileName: "/sessions/inspiring-funny-rubin/mnt/orchid/FORGE_PITCH_DECK.pptx" });

console.log("Forge pitch deck created successfully!");
