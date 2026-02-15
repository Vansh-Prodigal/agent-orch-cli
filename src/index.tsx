#!/usr/bin/env node
import React from "react";
import { render } from "ink";
import meow from "meow";
import { App } from "./App.js";

const cli = meow(
  `
  Usage
    $ proagent [options]

  Options
    --to-number, -t      Phone number to look up remote config
    --from-number, -f    Caller phone number (default: +10000000000)
    --config, -c         Path to local config JSON file
    --override, -o       Path to config override JSON (merged on top)
    --load-session, -l   Path to a saved session or chat export to resume
    --python, -p         Path to Python interpreter
    --project-root       Path to project root (default: auto-detect)

  Examples
    $ proagent --to-number +12025551234
    $ proagent --config simulator/chat_config.json
    $ proagent --to-number +12025551234 --override my_overrides.json
    $ proagent --load-session exports/sessions/session_2024-01-01.json
    $ proagent --load-session exports/chats/chat_xxx.json --config new_config.json
    $ proagent --load-session exports/chats/chat_xxx.json --to-number +12025551234
`,
  {
    importMeta: import.meta,
    flags: {
      toNumber: {
        type: "string",
        shortFlag: "t",
      },
      fromNumber: {
        type: "string",
        shortFlag: "f",
      },
      config: {
        type: "string",
        shortFlag: "c",
      },
      override: {
        type: "string",
        shortFlag: "o",
      },
      loadSession: {
        type: "string",
        shortFlag: "l",
      },
      python: {
        type: "string",
        shortFlag: "p",
      },
      projectRoot: {
        type: "string",
      },
    },
  },
);

render(
  <App
    toNumber={cli.flags.toNumber}
    fromNumber={cli.flags.fromNumber}
    configPath={cli.flags.config}
    configOverridePath={cli.flags.override}
    loadSessionPath={cli.flags.loadSession}
    pythonPath={cli.flags.python}
    projectRoot={cli.flags.projectRoot}
  />,
);
