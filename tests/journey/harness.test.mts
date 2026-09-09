import assert from "node:assert/strict";
import test from "node:test";

import {
  dockerContainerExists,
  startProcess,
  waitForHttp,
  withDisposablePostgres,
} from "./harness.mts";

test("the disposable database has one Alembic head and is removed", async () => {
  let containerName = "";

  await withDisposablePostgres(async (database) => {
    containerName = database.containerName;
    assert.equal(database.query("SELECT count(*) FROM alembic_version;"), "1");
    assert.equal(
      database.query("SELECT version_num FROM alembic_version;"),
      "0007_plan_revision",
    );
  });

  assert.equal(dockerContainerExists(containerName), false);
});

for (const processName of ["FastAPI", "Next.js"]) {
  test(`${processName} startup failure stops the journey loudly`, async () => {
    const failed = startProcess(
      processName,
      process.execPath,
      ["-e", "process.exit(17)"],
      process.env,
    );

    await assert.rejects(
      waitForHttp(
        processName,
        "http://127.0.0.1:1/not-listening",
        failed,
        2_000,
      ),
      new RegExp(`${processName} exited before becoming ready`),
    );
  });
}
