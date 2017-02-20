# Notable Tubes Transfer System

A chemical transfer tracker app written in Django Rest Framework, written for an interview take-home exercise. I got a bit overexcited and ended up implementing pretty much everything in the spec.... (partly as an opportunity to learn Django Rest Framework (it's a pretty neat framework, in my opinion!))

## Setup
    
#### _Optional_: set up a virtualenv**

	$ virtualenv env
	$ source env/bin/activate

#### Install dependencies

    $ pip install -r requirements.txt

#### Set up django and load initial data

    $ python manage.py migrate
    $ python manage.py loaddata tubes/fixtures/initial_data.json
    
#### Run tests and run the server

    $ python manage.py test
    $ python manage.py runserver

## Trying it out
#### Brief demonstration
Just run `./do_transfer.sh` to see the results before/after a transfer, as specified in the brief.

#### Endpoints
To get the container data as JSON, navigate to `http://127.0.0.1:8000/containers.json` or specify JSON in the Accept header.

The transfer endpoint is `POST http://127.0.0.1:8000/containers/<id>/transfer`, requiring json data `{'into': <id>}`.

#### Extras
Although the task specified that you didn't need a front end, Django Rest Framework gives us one for free! You can navigate to  `http://127.0.0.1:8000/containers` to see containers A and B with the expected data. 

If you care to, you can create a superuser with `./manage.py createsuperuser`, then log into admin mode at `http://127.0.0.1:8000/admin` to get a full view of the databse.

## Answers to the questions


#### How will you handle units in the app?
Units are handled using the _Unit_ model/table, which converts to/from millilitres. All volumes are given in terms of quantity and unit, and calculations are done in millilitres then converted back.

#### How do you ensure that you don't overdraw from a tube?
Since I have defined a transfer as simply "pour everything from A into B", overdrawing is impossible. A future possible solution would simply check that the requested volume is less than the current volume.

#### How do you ensure that you don't overfill a tube?
This is done before a transfer, in `models.py TransferPlan.execute() `, which simply checks if `A.content_volume + B.content_volume > B.container_volume`. If it fails, the a database transaction rolls everything back.

Currently there is no validation in the Container model itself, but it would not be too hard to add.

#### How do you handle tubes of varying dimensions?
I assume that the only thing which matters is volume. There is a _ContainerKind_ model/table which specifies a type-name and a volume, e.g. "TubeCorp TestTube, 1ml". Each Contaier links to a ContainerKind.

#### How will you handle authentication and logging who is creating the transfer?

Django Rest Framework handles this for us, with built in support for users and token/session based authentication. Session based authentication is useful for web-based API clients, token authentication would probably be ideal for any impementation on a lab machine. The code could easily be modified to be machine aware, e.g. with a new _Machine_ model (linked to transfers), and an `is_machine` User field.

#### Assume that the system is used for planning out transfers to happen in the future (by a scientist with a pipette). How does the system track this state? How do you ensure that a tube isn't overdrawn or overfilled with this system?

My implementation takes care of this using _TransferGroup_  - a list of _TransferPlans_.  When the group is executed, each transfer is executed sequentially and if any of them fail (due to overfilling), a database transaction automatically rolls back the entire operation.

#### How does the system adapt if scientists also want to track a transfer of another drug (like 0.2 milliliter of Bortezomib, another chemotherapy, at 100 micromolar) from a Tube C into Tube B. You can assume that the initial transfer of Cytarabine completes first.

My system takes care of this with _Substance_ and _Unit_ models. A substance can be anything, and each container can only contain 'one' of each substance, along with a quantity and a unit. Cells would have their own substance and unit, which specifies that kind of cell's volume/quantity. Overfilling and verification checks take all the contents of a container into account.

#### Given the basic use case, assume that Tube B is no longer empty initially but actually contains 0.5 milliliter of solvent, Dimethyl Sulfoxide. Also assume that the Cytarabine in Tube A is dissolved in the solvent Dimethyl Sulfoxide. What happens to the concentration of the Cytarabine when it is transferred from Tube A to Tube B? How does the system track this?

In this situation, the Cytarabine would be diluted. My system takes differing concentrations into account (see `test.py test_transfer_into_same_substance()`), and could model this situation with a tube that has Cytrabine at `concentration=0, volume=0.5`. However, it does not take other chemicals' concentrations into account (they are assumed to be separate), and also can not model multiple kinds of solvent.

#### Adding some solvents to a tube containing a drug solution could potentially result in non-terminating decimals in concentrations (i.e. 333.333 micromolar). How will the system handle rounding and displaying these concentrations?

I have not dealt with this in the code. The display aspect of this would be easy - numbers could be rounded to 0.001 or displayed as partial fractions with the Python [fractions](https://docs.python.org/2/library/fractions.html) module. If rounding errors severely impacted the model accuracy, I would have to consider other ways of storing/calculating concentrations.

## Appendix/Notes on the code

#### Structure
Since this is a django project, there is a fair bit of django boilerplate. Most of _my_ code is in the following files:

- `tubes/models.py`: contains all database models and business logic. In particular, _TransferPlan_ contains most of the logic for a transfer.
- `tubes/serializers.py`: specifies how output should be structured.
- `tubes/views.py`: implements the endpoints for containers and transfers. Django Rest Framework does a lot of heavy lifting here - only `transfer()` needed to be added manually.
- `tubes/urls.py`: configures the URL routes for the view, almost entirely automatically.
- `tubes/tests.py`: contains tests to ensure transfers succeed/fail as expected, and also tests the authentication system.

#### Query Optimization
There is function in particular I would like to draw your attention to, in `models.py`:
```
def get_full_queryset(cls):
    return cls.objects.select_related().prefetch_related(Prefetch('contents', queryset=Content.objects.select_related()))
```
One problem with Django is that - used naively - fetches can generate massive numbers of queries since the ORM doesn't know what to join and what to pre-fetch, so _Unit_, _ContainerKind_, etc. get fetched for each chemical and each container i.e. O(N) fetches:
```
(0.001) SELECT "tubes_container"."id", "tubes_container"."name", "tubes_container"."kind_id" FROM "tubes_container"; args=()
(0.000) SELECT "tubes_containerkind"."id", "tubes_containerkind"."quantity", "tubes_containerkind"."unit_id", "tubes_containerkind"."name" FROM "tubes_containerkind" WHERE "tubes_containerkind"."id" = 1; args=(1,)
(0.000) SELECT "tubes_unit"."id", "tubes_unit"."short_name", "tubes_unit"."long_name", "tubes_unit"."to_ml" FROM "tubes_unit" WHERE "tubes_unit"."id" = 1; args=(1,)
(0.000) SELECT "tubes_content"."id", "tubes_content"."quantity", "tubes_content"."unit_id", "tubes_content"."substance_id", "tubes_content"."container_id", "tubes_content"."concentration" FROM "tubes_content" WHERE "tubes_content"."container_id" = 1; args=(1,)
(0.000) SELECT "tubes_substance"."id", "tubes_substance"."name" FROM "tubes_substance" WHERE "tubes_substance"."id" = 1; args=(1,)
(0.000) SELECT "tubes_unit"."id", "tubes_unit"."short_name", "tubes_unit"."long_name", "tubes_unit"."to_ml" FROM "tubes_unit" WHERE "tubes_unit"."id" = 1; args=(1,)
(0.000) SELECT "tubes_substance"."id", "tubes_substance"."name" FROM "tubes_substance" WHERE "tubes_substance"."id" = 2; args=(2,)
(0.000) SELECT "tubes_unit"."id", "tubes_unit"."short_name", "tubes_unit"."long_name", "tubes_unit"."to_ml" FROM "tubes_unit" WHERE "tubes_unit"."id" = 1; args=(1,)
(0.000) SELECT SUM(("tubes_content"."quantity" * "tubes_unit"."to_ml")) AS "content_volume" FROM "tubes_content" INNER JOIN "tubes_unit" ON ("tubes_content"."unit_id" = "tubes_unit"."id") WHERE "tubes_content"."container_id" = 1; args=(1,)
(0.000) SELECT "tubes_containerkind"."id", "tubes_containerkind"."quantity", "tubes_containerkind"."unit_id", "tubes_containerkind"."name" FROM "tubes_containerkind" WHERE "tubes_containerkind"."id" = 1; args=(1,)
(0.000) SELECT "tubes_unit"."id", "tubes_unit"."short_name", "tubes_unit"."long_name", "tubes_unit"."to_ml" FROM "tubes_unit" WHERE "tubes_unit"."id" = 1; args=(1,)
(0.000) SELECT "tubes_content"."id", "tubes_content"."quantity", "tubes_content"."unit_id", "tubes_content"."substance_id", "tubes_content"."container_id", "tubes_content"."concentration" FROM "tubes_content" WHERE "tubes_content"."container_id" = 2; args=(2,)
(0.000) SELECT SUM(("tubes_content"."quantity" * "tubes_unit"."to_ml")) AS "content_volume" FROM "tubes_content" INNER JOIN "tubes_unit" ON ("tubes_content"."unit_id" = "tubes_unit"."id") WHERE "tubes_content"."container_id" = 2; args=(2,)
[04/Feb/2017 03:07:27] "GET /containers.json HTTP/1.1" 200 347
```

With this function, the ORM is instructed to fetch everything in advance and JOIN on related tables:

```
(0.001) SELECT "tubes_container"."id", "tubes_container"."name", "tubes_container"."kind_id", "tubes_containerkind"."id", "tubes_containerkind"."quantity", "tubes_containerkind"."unit_id", "tubes_containerkind"."name", "tubes_unit"."id", "tubes_unit"."short_name", "tubes_unit"."long_name", "tubes_unit"."to_ml" FROM "tubes_container" INNER JOIN "tubes_containerkind" ON ("tubes_container"."kind_id" = "tubes_containerkind"."id") INNER JOIN "tubes_unit" ON ("tubes_containerkind"."unit_id" = "tubes_unit"."id"); args=()
(0.000) SELECT "tubes_content"."id", "tubes_content"."quantity", "tubes_content"."unit_id", "tubes_content"."substance_id", "tubes_content"."container_id", "tubes_content"."concentration", "tubes_unit"."id", "tubes_unit"."short_name", "tubes_unit"."long_name", "tubes_unit"."to_ml", "tubes_substance"."id", "tubes_substance"."name", "tubes_container"."id", "tubes_container"."name", "tubes_container"."kind_id", "tubes_containerkind"."id", "tubes_containerkind"."quantity", "tubes_containerkind"."unit_id", "tubes_containerkind"."name", T6."id", T6."short_name", T6."long_name", T6."to_ml" FROM "tubes_content" INNER JOIN "tubes_container" ON ("tubes_content"."container_id" = "tubes_container"."id") INNER JOIN "tubes_unit" ON ("tubes_content"."unit_id" = "tubes_unit"."id") INNER JOIN "tubes_substance" ON ("tubes_content"."substance_id" = "tubes_substance"."id") INNER JOIN "tubes_containerkind" ON ("tubes_container"."kind_id" = "tubes_containerkind"."id") INNER JOIN "tubes_unit" T6 ON ("tubes_containerkind"."unit_id" = T6."id") WHERE "tubes_content"."container_id" IN (1, 2); args=(1, 2)
(0.000) SELECT SUM(("tubes_content"."quantity" * "tubes_unit"."to_ml")) AS "content_volume" FROM "tubes_content" INNER JOIN "tubes_unit" ON ("tubes_content"."unit_id" = "tubes_unit"."id") WHERE "tubes_content"."container_id" = 1; args=(1,)
(0.000) SELECT SUM(("tubes_content"."quantity" * "tubes_unit"."to_ml")) AS "content_volume" FROM "tubes_content" INNER JOIN "tubes_unit" ON ("tubes_content"."unit_id" = "tubes_unit"."id") WHERE "tubes_content"."container_id" = 2; args=(2,)
```

The volume aggregates are still computed once for each container, but everything else is fetched in two big requests, no matter how many containers there are and what they contain.

`LOG_SQL = True` can be set in `settings.py` to see these SQL logs.
