<!--
SPDX-FileCopyrightText: 2023 Mewbot Developers <mewbot@quicksilver.london>

SPDX-License-Identifier: BSD-2-Clause
-->

Note - This plugin went through a fairly extensive set of evolutions before settling into it's current form.

It started life as "I want a way to write data to disk".
It then evolved to "I want to do that, and be notified when data is written to disk."

These turned out to be very different problems - so they've now been split down into two plugins.

Below are the original notes written when they were being developed as a single plugin.

Please see `file-system-input-dev-notes.md` for the input side.
Notes might not exist for the output side - or I might get round to writing some if they're needed.

## Legacy Notes

### Objective

Generate events on file system changes for input.

Write objects/text out to local files for output (helpful for in bot logging/auditing/archiving).

### Underlying library

[watchfiles][1]

Upsides - fast. Simple.

Downsides - Uses a compiled rust backend which might cause some problems in some edge cases.

### Input

File system events - should be able to monitor individual files and folders separately.

Probably want separate events for files and folders - and for various tasks which could be preformed on them

Files

* Creation - Probably should contain
  * File name
  * Creation time - probably just a unix timestamp for simplicity
  * File size
  * Entire file - should be included as an option - there are some cases where it could be really useful - some cases where it would be better to let the Actions handle their own io. Should probably default to not being included. Default read mode ... just "r" at a guess. But that also needs to be user settable. And in the event so people know
* Deletion
  * File name
  * Deletion time
  * No good way to include file size without a running cache of all file sizes - which could get very large depending on the file system - out of scope. Should be handled by an action if required.
  * No good way to include the entire file without a running cache of all the files in the dir in memory. Suspect this is out of scope.
* Update
  * File name
  * Update time
  * Likewise no way to include the size delta - because of the aforementioned cache issue - so just include size
  * Optionally the current state of the file

Dirs

* Creation
  * Dir name
  * Creation time (unix timestamp as above - in fact - could we standardize to using unix timestamps internally?)
* Update - there are a few different forms an update to a folder could take
  * Folder rename event
    * If this is a rename of the folder being monitored ... then we're going to (probably) loose it - as we don't necessarily know the new name to keep monitoring.
    * Need to check to see if this looks like a delete event
    * rename of an asset in the folder being monitored ... unless this ends up involving a full dir tree traversal every update. In which case, no.
  * Folder delete event
    * And for any asset in this folder

So there seems to be two different operational modes
 * The input class is pointed at a file - in which case it keeps an eye on the file location. If it's deleted, it tells the user, if it's added to, it tells the user. Possibly can't easily tell the difference between a rename and a delete. Will see what the library gives us.
 * The input class is pointed at a folder. So it looks for changes to the contents of the folder.

Don't think it's useful to draw a distinction between if the change is to the sole file monitored or a file in the dir being monitored

### Input events

 - FileCreatedInputEvent
 - FileUpdatedInputEvent - in the future - adding options for owner and permission bit updates? But not in the prototype.
 - FileRenamedInputEvent (might just end up bein a Deleted and a Created)
 - FileDeletedInputEvent
 - DirCreatedInputEvent
 - DirUpdatedInputEvent - when the contents of the folder are updated it'll spew appropriate file events - so this is for when the name of the folder is updated.
 - DirDeletedInputEvent - when the monitored dir - or stuff inside it - is deleted. Note - not sure if we can - or if we want to - also spawn deletion events for all the stuff inside it. This might be preferable, but might also present a considerable technical challenge.

(Names swapped around in the code to create an actually coherent class hierarchy and naming convention - curse you English).

On declaring the file mode in the event dataclass ref this discussion [here][2]. This convinced me to just include the modes in the event dataclass - seemed easier.

### Output events

So this was originally conceived because I just wanted to be able to dump the raw text of discord messages out to disk without having to handle the fileIO in an action. It then occurred that being able to monitor files for input events would be useful - the use case I thought of was causing input events whenever log files where updated.

Bearing in mind that the prototypical use case is just "I want the contents of this message file on disk"

So just supporting file creation - for now.

Also worth being aware of the concerning of infinite loops - writing output files back into the monitored input folder.

Note - some care going to have to be taken with security - something like PyFS - which limits where you can make files and folders - for the moment just forcing people to specify a folder that they want stuff to be created in.
This may be relaxed - with caution - later.

File output events
* Create a file - needs the name of the file and the contents
* Append to a file - the name of the file and the contents
* Overwrite a file - likewise
* Delete a file - just the name of the file to remove should be enough

### The IO Config

Currently, we're defining an input path and an output path. The input path is monitored for input and the output path has output written out to it.

HOWEVER - neither of these are necessary to the function of the other - so if an input_path is not provided, then the IOConfig should not have an input - until such time as a path is provided - which it might be later, on the hoof as it where. But this might screw things up upstream - not sure the framework can cope at present with transitory inputs - so there should always be an input - it should just do nothing until given a sensible thing to monitor.

Would it be best to give it the capacity to monitor multiple different files - or would be best to just force people to define several different IO Configs?

Probably, for simplicity, best for people to define multiple different IO Configs - but that might be a mistake.

### Limitations of the library - or, perhaps, the file system

Watchfiles tells us if a file or files in a folder has been modified.

Which probably means that we need to check what the resource is when it's modified ... could just collapse the file and the folder Inputs into a single class ... but that would make the input method a bit less helpful.

Instead - after some research (and some "implementing it badly myself") there are two main options.

[aiofiles][3] - Which has a pathlib built in - but just seems to be a thin wrapper based on running everything in executors - which is not bad, per se, but could be a lot better
[aiopath][4] - Which seems to be a less naive and - probably - more efficient implementation. And also seems capable of handling file io

(Note - there seem to be two different projects - aiofile and aiofiles - file seems better than files, and is included in aiopath as a dependency).

So rolling with aiopath for the moment - may revisit later.

Current we get back a tuple containing the type of change and the path to the changed resource. But not the modification time ... 
Cam retrieve that later ... or just not bother.

### Bug 1 - watchfiles throws a FileNotFound error when the file does not, in fact, exist

This is ... less than idea. It would be better if the watcher just waited until the file appeared.

There seems to be no easy way to change this behavior other than digging into the compiled Rust directly.

Additionally - monitoring files in a folder seems to work well - assuming the folder exists at startup. If the folder does not - and is created later - it breaks. If the folder initially exists, and then is deleted, and then is recreated, it seems to _silently_ break.

It's probably monitoring the linode id - or equivalent - so new dir, new id.
In keeping with this guess - deleting and recreating a file triggers the same problem.

So - probably going to need two operational modes - one where the system polls the file every (interval) using some kind of async path check - and one where watchfiles just watches it.

Mode determined by switching on startup and on delete events which correspond to the file path being monitored.

It was around this point that I realised that more comprehensive testing would be required. 

### More comprehensive testing required

Ideally, it would be best to just run an entire bot, with some custom methods for testing thrown in.
But the input component is now gnarly enough I want to test it individually.

Using [pytest-asyncio][5] and just enough infrastructure to isolate the input.
The advantage of this is it demonstrates that the inputs can be pulled out and resumed fairly easily - which is good for re-usability.

### More problems with the library

So - there are a number of issues

the watchfiles watcher explodes when it's fed a bad path to begin with.
This has been corrected by the two operational modes mentioned above.
But it also explodes - somewhat less helpfully - when you delete and recreate the file during a run.
So going to have to build some infrastructure around this to deal with that and to elegantly resume after the errors.
And to detect if the folder it's monitoring itself has been deleted...
Might be worth considering breaking the input down into a "folder monitor" and a "file monitor" - but I still think this is the wrong approach.
It makes handling such cases as "what if we started monitoring a file, then someone deleted it and replaced it with a folder" quite a lot harder.
If it's watching a folder, and the folder gets deleted, it explodes halfway through notifying you about all the deletion events - this is clearly not on, and something needs to be done. 

To be fair to it, watchfiles was, by the name, not really intended to deal with folders.

### Alternatives

[aiowatcher][7] - looks ... fairly sane. Not for windows tho.
[watchgod][8] - Has been renamed to watchfiles ... the package we're using. Note - the name put me off a bit, but I'm now pretty sure it's a play on the old project watchdog.
[pyinotify][9] - Years out of date and not sure that it would play nice with async (as the last time it was updated was python 3.6)
[minotaur][10] - Looks fairly sane - but a young project which hasn't been updated for six months. However, it did recommend (with the caveat it doesn't have a non-async interface).
Almost certainly will not work on windows.
[asyncinotify][11] which just looks really sensible
[butter][12] does not work under windows.
I would, in fact, be _greatly_ surprised if anything inotify based worked under windows. Due to windows, you know, not having inotify. But, apparently, there are some equivalent C based options on windows. So giving it a try.

So giving asyncinotify a crack!

Turns out, dll load changes in python 3.8 have completely broken it.

So working up something with watchdog instead.

------- 

COPIED FORM ASYNCINOTIFY FOR EMPHASIS - THIS PERSUADED ME TO SWITCH FROM USING STRINGS FOR THE PATHS TO pathlib.Path instances

Warning
This package handles the watch paths and event names and paths as pathlib.Path instances. These may not be valid utf-8, because Linux paths may contain any character except for the null byte, including invalid utf-8 sequences. This library encodes these using python’s surrogateescape handler, to conform to the way the os package does it. This means that if you have invalid utf-8 in a path, you can still handle it correctly and reference it as a file, but if you try to print it or convert it (such as using the str.encode() method), you will get an error unless you explicitly use surrogateescape.

You can read more about the surrogateescape in the Python os package documentation and the codecs error handler documentation.

-------

There was a helpful gist for incorporating watchdog with async [here][13]. Using this as the basis for the method.

#### After some more experimentation, the pain continues

So - we now have two solutions that work pretty well - in different contexts.

watchfiles - works really quite well on one file (or many - but we're not really using the library to its full effect)

watchdog works really well on dirs.

Neither of them works great when you delete the location that they're monitoring.
Neither of them likes it if you remove the location they're monitoring and recreate it.

So probably need to use both for different operational modes - possibly with some mods so that the system knows when monitoring fails and to resume.

These operational modes - probably should be separate input classes on balance.
With the selection between them controlled by the type of resource the user declares it is - force them to be specific.
This seems less likely to lead to unexpected behavior (for example, the edge case of starting with a file, then the user deletes it, then they create a dir in its place. You might then get a bunch of file events - for files created in the new folder - which you might not reason about correctly.)

Note - there might not be a good way to tell what's going on - so it might be best to have SPECIFIC events for the monitoring target being created or deleted - so the user can watch for those explicitly, and not have to, e.g., check every dir deleted event in a dir monitoring scenario to see if it's the target directory which has been deleted).

In fact - that seems a necessary and obvious thing to do... so more refactoring and more work on the examples.

#### Actually, that didn't help so much

Turns out the problem may be more with how windows monitors files through it's internal api than with watchdog/watchfiles itself.

In particular, the problem which is currently proving to be an issue is the fact that events are being produced out of order - or, at least, in an unhelpful order.
So you might get a couple of file modified events before finally getting the deleted one.
Or, perhaps, a move event might occur and put a new file in the place of the deleted on - so you get a deletion event for a file which is, in fact, still there.
This is something of a difficulty.

Best way I've come up with so far
* every time there is a modification event, check to see if the file still exists
  * If the file does not exist - check the cache to see if we've notified the user and, if we have, do nothing. If we have not, then send the event and note it in the cache
  * If the file does exist then emit the event as normal
* If the system acknowledges the delete, then there seem to be no more modification events - so you can remove the file from the cache. If we see any more changes, then it's (probably) for a new file which has replaced the old one.

Hopefully, once a file has been moved into place of the old one, then any modification or move events are legit.

Thought - as the logic of this whole process is getting quite involved, it might be for the best if the user can just inform the system that they just want the raw events coming off the watcher.
Incase the additionally caching and other stuff is proving unhelpful.

#### Am I just doing Windows file monitoring very wrong?

ENTIRELY possible!

So the watcher seemed to be producing Windows file events in what can only be characterised as a suboptimal manner.
Though I'm sorta just hoping I'm doing it wrong in some way.

Take a file - then delete it.
 - You will not, necessarily, get a clean deletion event.
 - Instead, you seem to get a number of update events - then the deletion event
 - Unless you _immediately_ create a new file in its place. In which case, you sometimes never get the delete action - sometimes - and instead get more update actions
 - Moving files around also seems to cause some confusion - though that might be more of a python thing.
 - Sometimes - the ordering is not what one might call regular. 
 - Sometimes events are delayed until after other events - for some reason.
 - But not always.
 - Testing this is proving to be a bit of an issue (thing I might move to a promise model - break it down for each file and dir, and at least check that events concerning them are arriving in the right order)

I've tried to implement some smoothing - using os calls to tell if a file is _really_ gone or not, and then shaping the actual events produced appropriately.
The best I've been able to come up with so far for an algorithm is as follows.

Solved this problem - with some caching and some checking of the actual files on disk - less than ideal and does result in more disk churn than I would like - but seemed the only way to run it.

Then it turned out that the monitor sometimes (often) confuses dirs and files.
So I spun the entire watcher out into an os specific class - because now it's having to do a lot of computational grunt work to actually ensure the events reflect reality - and none of that should be necessary on linux e.t.c.
This turns out to also be an issue for move events - going to experiment with different backends.
But, for the moment, the situation has been fixed with some caching and parsing to try and force the output of the class to conform to something resembling reality.
This was augmented with check calls using os.path.exists
This solution is less than elegant, and probably horribly inefficient. But it works. Ish.
New backend for linux will follow. When I regain the will.

NOTE - I regained the will. But immediately encountered another set of problems.

#### Standardization of output

So the problem seems to be that the windows and linux file monitors just produce some fundamentally different outputs.

I've done some tuning of the windows output to more closely match the linux one - but there ate just too many points where they were different to really make it practical to really make them line up 100 percent.
(There's stuff you could do - more parsing and caching of items - interruptable delays before putting more files on the wire - that sort of approach. But it's looking like a rather large amount of work and what's there seems good enough.)

AS SUCH - DIR MONITOR OUTPUT IS GOING T0 BE OS DEPENDANT.

Sorry.

There are tests for the windows and for other (linux) like output events - and some smoothing has been done on the windows side to make things more like the linux side. But it's not 100 percent.
Tests are, however, present for both windows and linux systems to illustrate the differences.

### Output

For the moment only supporting writing files into a directory (subfolders e.t.c can wait).
And only supporting
 - creation
 - update - appending
 - overwrite
 - deletion
For simplicity, all 16 of the basic write modes ARE NOT supported - just these four (well - eight - as you can toggle binary on and off)

These events must be explicitly created - and will fail.
To stop the proliferation of message classes, there's a switch in the base class for binary or not.

### Testing

Has, in common with almost every other part of this module, proven to be a bit of an issue.
The number and type of events produced by the underlying API seems to vary somewhat - annoyingly, not predictably.
So you might get a semi-random number of update events before a delete - for examples.
Hence - use the input part of this module with caution.
It'll _mostly_ work - you do tend to always get creation events when a file or dir is created - likewise update events _mostly_ just mean something has been updated.
Or created.
Or is about to be deleted.
Exercise caution, is what I'm saying here.

NOTE FOR THE FAR FUTURE

I have some vague notions about it being a really good idea if mewbot could (easily) stand being a distributed system. Not for reasons of running many, many bots at once. 
Not for reasons of scale - we're currently not even really allowing ourselves more than one thread, but for reasons of flexibility. 
Running some IO methods on linux is looking like a pain.

Or this might be way more trouble than it's worth.

Long story short? 
You might be surprised when you feel the file_path variable from the IO dataclassess into a local os.path function.
Unexpected behavior may result.

I have the feeling that some IO methods - such as this one - might be a pain in the arse.

Using [pytest-asyncio][5] seemed the best supported testing extension for async code. Adding this to requirements-dev.txt.

[alt-pytest-asyncio][6] was considered, but the fact it only used one loop for all the tests made it seem worse than [pytest-asyncio][5] - which also seemed more full featured.


[1]: https://github.com/samuelcolvin/watchfiles "Watchfiles"
[2]: https://discuss.python.org/t/enum-for-open-modes/2445/4 "File mode enum discussion"
[3]: https://github.com/Tinche/aiofiles "aiofiles"
[4]: https://github.com/alexdelorenzo/aiopath "aiopath"
[5]: https://pypi.org/project/pytest-asyncio/ "pytest-asyncio"
[6]: https://pypi.org/project/alt-pytest-asyncio/ "alt-pytest-asyncio"
[7]: https://pypi.org/project/aiowatcher/ "aiowatcher"
[8]: https://pypi.org/project/watchgod/ "watchgod"
[9]: https://github.com/seb-m/pyinotify "pyinotify"
[10]: https://github.com/giannitedesco/minotaur "minotaur"
[11]: https://asyncinotify.readthedocs.io/en/latest/ "asyncinotify"
[12]: "https://pypi.org/project/butter/" "butter"
[13]: "https://gist.github.com/mivade/f4cb26c282d421a62e8b9a341c7c65f6" "helpful watchdog with async gist"